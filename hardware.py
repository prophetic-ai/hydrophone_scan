"""
Hardware control for Hydrophone Scanner
Handles Arduino and Oscilloscope communication.
"""

import serial
import time
import logging
import numpy as np
from typing import Dict, Tuple
import pyvisa
from tqdm import tqdm
import json


class HardwareController:

   def __init__(self, arduino_port: str, scope_address: str = None, config: Dict = None):
       self.arduino_port = arduino_port
       self.scope_address = scope_address
       self.config = config
       self.arduino = None
       self.scope = None
       self.scope_type = None
       self.current_position = {'x': 0, 'y': 0, 'z': 0}
       self.scale_history = None
       
       self.auto_scaling_enabled = self.config['hardware'].get('auto_scaling_enabled', True)  # Default to True if not specified


       self.MM_PER_STEP = {
           'x': 1 / self.config['hardware']['steps_per_mm']['x'],
           'y': 1 / self.config['hardware']['steps_per_mm']['y'],
           'z': 1 / self.config['hardware']['steps_per_mm']['z']
        }

       # Constants for vertical scaling
    #    self.UPPER_LIMIT = 90
    #    self.LOWER_LIMIT = 20
    #    self.ROUND_BIN = 20e-3  # 20mV

       # Track current scale to avoid unnecessary logging
       self.current_scale = 0.1  # Start at 100mV/div
       self.last_scale_change = 0  # Time of last scale change

       self._setup_connections()

   def _setup_connections(self) -> None:
       """Establish hardware connections"""
       try:
           print("\nConnecting to Arduino...")
           self.arduino = serial.Serial(
               port=self.arduino_port,
               baudrate=115200,
               timeout=1
           )
           time.sleep(2)

           response = self.arduino.readline().decode().strip()
           if not "Arduino is ready" in response:
               raise ConnectionError("Arduino not responding correctly")
           print("Arduino connected successfully")

       except serial.SerialException as e:
           raise ConnectionError(f"Failed to connect to Arduino: {e}")

       if self.scope_address:
           try:
               print("\nConnecting to oscilloscope...")
               rm = pyvisa.ResourceManager()
               self.scope = rm.open_resource(self.scope_address)
               self.scope.timeout = 30000

               # Reset and clear
               self.scope.write('*RST')
               time.sleep(2)
               self.scope.write('*CLS')
               time.sleep(1)

               # Get scope settings from config
               settings = self.config['hardware']['scope_settings']

               # Verify basic communication
               idn = self.scope.query('*IDN?')
               print(f"Connected to scope: {idn}")

               # Detect scope type
               if 'TEKTRONIX' in idn.upper():
                   self.scope_type = 'TEKTRONIX'
                   commands = [
                       f'CH1:COUPLING {settings["channel_coupling"]}',
                       f'CH1:SCALE {settings["vertical_scale"]}',
                       f'CH1:POSITION {settings["channel_position"]}',
                       f'HOR:SCALE {settings["horizontal_scale"]}',
                       f'TRIGger:MAIn:EDGE:SOUrce {settings["trigger_source"]}',
                       f'TRIGger:MAIn:EDGE:SLOpe {settings["trigger_slope"]}',
                       f'TRIGger:MAIn:MODe {settings["trigger_mode"]}',
                       f'TRIGger:MAIn:EDGE:COUPling {settings["trigger_coupling"]}',
                       f'TRIGger:MAIn:LEVel {settings.get("trigger_level", 1.0)}',
                       f'ACQuire:MODe {settings.get("acquisition_mode", "SAMPLE")}',
                       f'ACQuire:NUMAVg {settings.get("average_count", 16)}' if settings.get(
                           "acquisition_mode") == "AVERAGE" else None,
                       'DATA:SOURCE CH1',
                       'DATA:WIDTH 1',
                       'DATA:ENCDG RIBINARY'
                   ]

                   # Filter out None values
                   commands = [cmd for cmd in commands if cmd is not None]

               elif 'SIGLENT' in idn.upper():
                   self.scope_type = 'SIGLENT'
                   commands = [
                       'CHDR OFF',
                       f'C1:CPL {settings["channel_coupling"]}',
                       f'C1:VDIV {settings["vertical_scale"]}V',
                       f'TDIV {settings["horizontal_scale"]}',
                       f'TRSE EDGE,SR,{settings["trigger_source"]}',
                       f'TRLV {settings.get("trigger_level", 1.0)}V',
                       f'EX:TRSL {settings["trigger_slope"]}',
                       f'TRMD {settings["trigger_mode"]}',
                       f'C1:TRCP {settings["trigger_coupling"]}',
                       f'ACQW {settings.get("acquisition_mode", "SAMPLING")}',
                       f'AVGA {settings.get("average_count", 16)}' if settings.get(
                           "acquisition_mode") == "AVERAGE" else None,
                       'MSIZ 14M',
                       'SARA?',
                       'WFSU SP,0,NP,0,FP,0'
                   ]

                   # Filter out None values
                   commands = [cmd for cmd in commands if cmd is not None]
               else:
                   raise ValueError(f"Unsupported oscilloscope: {idn}")

               print(f"Configuring {self.scope_type} scope settings...")
               for cmd in commands:
                   if '?' in cmd:
                       response = self.scope.query(cmd)
                       print(f"Query {cmd}: {response}")
                   else:
                       self.scope.write(cmd)
                       time.sleep(0.1)

               print("Scope configuration complete")

           except Exception as e:
               raise ConnectionError(
                   f"Failed to connect to oscilloscope: {str(e)}")

   def move_axis(self, axis: str, distance: float) -> bool:
       """Move specified axis by given distance"""
       if axis not in self.MM_PER_STEP:
            raise ValueError(f"Invalid axis: {axis}")

       try:
           steps = round(distance / self.MM_PER_STEP[axis])
           direction = '+' if distance > 0 else '-'
           command = f"<{axis},{direction},{abs(steps)}>"
           self.arduino.write(command.encode())
           self.arduino.flush()
           # Add position tracking
           self.current_position[axis] += distance
           return True

       except serial.SerialException as e:
           tqdm.write(f"Movement error: {e}")
           return False

   def get_current_position(self):
       """Return the current position"""
       return self.current_position


  
        
        


   def get_full_waveform(self) -> Tuple[np.ndarray, np.ndarray]:
       """Get complete waveform with time values"""
       if not self.scope:
           raise ConnectionError("Oscilloscope not connected")
           
       try:
           if self.scope_type == 'TEKTRONIX':
               self.scope.write('*CLS')
               self.scope.write('CURVE?')
               raw_wave = self.scope.read_raw()
               header_length = 2 + int(raw_wave[1:2])
               data = np.frombuffer(raw_wave[header_length:], dtype=np.int8)
               
               # Get scales
               hor_scale = float(self.scope.query("HORizontal:SCAle?"))
               y_offset = float(self.scope.query("WFMPre:YOFf?"))
               vert_scale = float(self.scope.query("WFMPre:YMUlt?"))
               
               # Calculate time values
               dt = hor_scale * 10 / len(data)
               time_array = np.arange(len(data)) * dt
               
               # Convert to voltage
               voltage_array = (data - y_offset) * vert_scale

           else:  # SIGLENT
               # Get waveform data
               self.scope.write('C1:WF? DAT2')
               raw_wave = self.scope.read_raw()
               data = np.frombuffer(raw_wave[15:-2], dtype=np.int8)
               
               # Get scales
               tdiv = float(self.scope.query('TDIV?').split()[-1].strip('S'))
               vdiv = float(self.scope.query('C1:VDIV?').split()[-1].strip('V'))
               offset = float(self.scope.query('C1:OFST?').split()[-1].strip('V'))
               sara = float(self.scope.query('SARA?').split()[-1].strip('Sa/s'))
               
               # Calculate time values
               dt = 1/sara
               time_array = np.arange(len(data)) * dt
               
               # Convert to voltage using Siglent scaling
               voltage_array = data * (vdiv/25) - offset
           
           waveform_data = {
               'time': time_array.tolist(),
               'voltage': voltage_array.tolist()
            }
           
        #    with open('waveform.json', 'w') as f:
        #        json.dump(waveform_data, f)

            
           return time_array, voltage_array
           
       except Exception as e:
           tqdm.write(f"Waveform acquisition error: {e}")
           return None, None

   def close(self):
       """Close hardware connections"""
       print("\nClosing hardware connections...")
       if self.arduino and self.arduino.is_open:
           self.arduino.close()
           print("Arduino disconnected")
       if self.scope:
           self.scope.close()
           print("Oscilloscope disconnected")




   ####### NEW SCALING ALGORITHM: #######

   def get_measurement(self) -> Tuple[float, float]:
       """Get single measurement from scope with voltage-based scaling"""
       if not self.scope:
           raise ConnectionError("Oscilloscope not connected")
            
       # Configuration constants
       MAX_SCALING_ATTEMPTS = 3
       SETTLING_TIMES = {
           'TEKTRONIX': 0.3,  # 300ms for Tektronix
           'SIGLENT': 0.2     # 200ms for Siglent
       }
       SCALE_LIMITS = {
           'min': 0.02,  # 2mV/div minimum 
           'max': 10.0    # 10V/div maximum
       }
       NOISE_FLOOR = 0.001  # 1mV noise floor estimation
       
       def get_scope_data():
           """Helper function to get data from scope"""
           try:
               if self.scope_type == 'TEKTRONIX':
                   self.scope.write('*CLS')
                   self.scope.write('CURVE?')
                   raw_wave = self.scope.read_raw()
                   header_length = 2 + int(raw_wave[1:2])
                   data = np.frombuffer(raw_wave[header_length:], dtype=np.int8)
                   
                   y_offset = float(self.scope.query("WFMPre:YOFf?"))
                   vert_scale = float(self.scope.query("WFMPre:YMUlt?"))
                   wave_volts = (data - y_offset) * vert_scale

               else:  # SIGLENT
                   self.scope.write('C1:WF? DAT2')
                   raw_wave = self.scope.read_raw()
                   data = np.frombuffer(raw_wave[15:-2], dtype=np.int8)
                   
                   vdiv = float(self.scope.query('C1:VDIV?').split()[-1].strip('V'))
                   offset = float(self.scope.query('C1:OFST?').split()[-1].strip('V'))
                   wave_volts = data * (vdiv/25) - offset
                   
               return wave_volts
               
           except Exception as e:
               logging.error(f"Scope data acquisition error: {e}")
               return None

       def set_scale(new_scale: float) -> bool:
           """Helper function to set scope scale"""
           try:
               if self.scope_type == 'TEKTRONIX':
                   self.scope.write(f"CH1:Scale {new_scale}")
               else:  # SIGLENT
                   self.scope.write(f"C1:VDIV {new_scale}V")
               
               time.sleep(SETTLING_TIMES[self.scope_type])
               return True
           except Exception as e:
               logging.error(f"Scale setting error: {e}")
               return False

       def calculate_new_scale(peak_to_peak: float, usage_percent: float) -> float:
           """Helper function to calculate new scale"""
           # Calculate target scale based on usage
           target_usage = 70  # Aim for 70% usage
           current_time = time.time()
           scale_age = current_time - self.last_scale_change
           
           # Add acceleration factor based on how far off we are
           acceleration = min(2.0, abs(target_usage - usage_percent) / 50)
           
           if usage_percent > 90 and scale_age > 2.0:
               # Scale up with acceleration
               scale_factor = min(1.5 * acceleration, 2.0)
               new_scale = min(SCALE_LIMITS['max'], 
                             self.current_scale * scale_factor)
               
           elif usage_percent < 5 and scale_age > 3.0:
               # Check if we're near noise floor
               if peak_to_peak < NOISE_FLOOR * 3:  # 3x noise floor minimum
                   return self.current_scale
                   
               # Scale down with acceleration
               scale_factor = max(0.75 / acceleration, 0.5)
               new_scale = max(SCALE_LIMITS['min'],
                             self.current_scale * scale_factor)
           else:
               return self.current_scale
               
           # Round to nearest standard scope scale
           standard_scales = [
               0.02,   # 20mV
               0.05,   # 50mV
               0.1,    # 100mV
               0.2,    # 200mV
               0.5,    # 500mV
               1.0,    # 1V
               2.0,    # 2V
               5.0,    # 5V
               10.0    # 10V
           ]
           
           return min(standard_scales, key=lambda x: abs(x - new_scale))

       # Main measurement loop
       for attempt in range(MAX_SCALING_ATTEMPTS):
           try:
               # Set initial scale
               if not set_scale(self.current_scale):
                   raise Exception("Failed to set initial scale")
                   
               # Get waveform data
               wave_volts = get_scope_data()
               if wave_volts is None:
                   raise Exception("Failed to get waveform data")
                   
               # Calculate measurements
               max_v = np.max(wave_volts)
               min_v = np.min(wave_volts)
               peak_to_peak = max_v - min_v
               display_range = self.current_scale * 8  # 8 divisions total
               usage_percent = (peak_to_peak / display_range) * 100
               
               # Update scale history with exponential moving average
               if self.scale_history is None:
                   self.scale_history = usage_percent
               else:
                   self.scale_history = self.scale_history * 0.7 + usage_percent * 0.3
               
               # Check if auto-scaling is enabled
               if self.auto_scaling_enabled:
                   # Calculate new scale if needed
                   new_scale = calculate_new_scale(peak_to_peak, usage_percent)
                   
                   # Apply new scale if significant change
                   if abs(new_scale - self.current_scale) / self.current_scale > 0.01:
                       if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                           tqdm.write(f"Signal scale adjustment ({attempt+1}/{MAX_SCALING_ATTEMPTS}): "
                                      f"{self.current_scale:.3f}V/div -> {new_scale:.3f}V/div")
                       
                       self.current_scale = new_scale
                       self.last_scale_change = time.time()
                       continue  # Try another measurement with new scale
               
               # If we get here, scale is good
               if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                   tqdm.write(f"Measurement: {max_v:.3f}V to {min_v:.3f}V "
                              f"(scale: {self.current_scale:.3f}V/div)")
               
               return max_v, min_v
               
           except Exception as e:
               logging.error(f"Measurement attempt {attempt+1} failed: {e}")
               if attempt == MAX_SCALING_ATTEMPTS - 1:
                   # On final attempt, return zeros and reset scale history
                   self.scale_history = 50
                   return 0.0, 0.0
               
               # Otherwise try again with current scale
               time.sleep(0.5)  # Add delay between retries