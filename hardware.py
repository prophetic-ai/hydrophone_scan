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

class HardwareController:
    MM_PER_STEP: Dict[str, float] = {
        'x': 0.01,
        'y': 0.01,
        'z': 0.01
    }
    
    def __init__(self, arduino_port: str, scope_address: str = None):
        self.arduino_port = arduino_port
        self.scope_address = scope_address
        self.arduino = None
        self.scope = None
        
        # Constants for vertical scaling
        self.UPPER_LIMIT = 90  
        self.LOWER_LIMIT = 20  
        self.ROUND_BIN = 20e-3  # 20mV
        
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
                
                # Verify basic communication
                idn = self.scope.query('*IDN?')
                print(f"Connected to scope: {idn}")
                
                print("Configuring scope settings...")
                # Setup commands matching MATLAB exactly
                commands = [
                    # Channel setup
                    'CH1:COUPLING AC',
                    'CH1:SCALE 1.0',
                    'CH1:POSITION 0',
                    
                    # Trigger setup
                    'TRIG:SOURCE EXT',
                    'TRIG:TYPE EDGE',
                    'TRIG:SLOPE RISing',
                    'TRIG:MODE AUTO',
                    'TRIG:COUPLING AC',
                    
                    # Data acquisition setup
                    'DATA:SOURCE CH1',
                    'DATA:WIDTH 1',
                    'DATA:ENCDG RIBINARY'
                ]
                
                for cmd in commands:
                    self.scope.write(cmd)
                    time.sleep(0.5)
                
                print("Scope configuration complete")
                    
            except Exception as e:
                raise ConnectionError(f"Failed to connect to oscilloscope: {str(e)}")

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
            return True
                
        except serial.SerialException as e:
            tqdm.write(f"Movement error: {e}")
            return False

    def get_measurement(self) -> Tuple[float, float]:
        """Get single measurement from scope with voltage-based scaling"""
        if not self.scope:
            raise ConnectionError("Oscilloscope not connected")
            
        try:
            # Set initial scale if needed
            self.scope.write(f'CH1:SCALE {self.current_scale}')
            time.sleep(0.1)
            
            # Get initial reading
            self.scope.write('*CLS')
            self.scope.write('CURVE?')
            raw_wave = self.scope.read_raw()
            header_length = 2 + int(raw_wave[1:2])
            data = np.frombuffer(raw_wave[header_length:], dtype=np.int8)
            
            # Convert to voltage
            y_offset = float(self.scope.query("WFMPre:YOFf?"))
            vert_scale = float(self.scope.query("WFMPre:YMUlt?"))
            wave_volts = (data - y_offset) * vert_scale
            max_v = np.max(wave_volts)
            min_v = np.min(wave_volts)
            
            # Only rescale if really necessary
            peak_to_peak = max_v - min_v
            new_scale = None
            
            # Check if we need to change scale
            if peak_to_peak > 0.8 * self.current_scale * 8:  # Using >80% of display
                new_scale = min(1.0, self.current_scale * 2)  # Don't go above 1V/div
            elif peak_to_peak < 0.1 * self.current_scale * 8 and self.current_scale > 0.02:  # Using <10% of display
                new_scale = max(0.02, self.current_scale * 0.5)  # Don't go below 20mV/div
                
            # Apply new scale if needed
            if new_scale and new_scale != self.current_scale:
                # Only log scale changes if they're not too frequent
                current_time = time.time()
                if current_time - self.last_scale_change > 1.0:  # Minimum 1 second between scale change messages
                    if new_scale > self.current_scale:
                        tqdm.write(f"Signal too large, scale -> {new_scale:.3f}V/div")
                    else:
                        tqdm.write(f"Signal too small, scale -> {new_scale:.3f}V/div")
                    self.last_scale_change = current_time
                
                self.current_scale = new_scale
                self.scope.write(f"CH1:Scale {self.current_scale}")
                time.sleep(0.1)
                
                # Get new reading
                self.scope.write('CURVE?')
                raw_wave = self.scope.read_raw()
                header_length = 2 + int(raw_wave[1:2])
                data = np.frombuffer(raw_wave[header_length:], dtype=np.int8)
                y_offset = float(self.scope.query("WFMPre:YOFf?"))
                vert_scale = float(self.scope.query("WFMPre:YMUlt?"))
                wave_volts = (data - y_offset) * vert_scale
                max_v = np.max(wave_volts)
                min_v = np.min(wave_volts)
            
            # Only log measurements in debug mode
            if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
                tqdm.write(f"Measurement: {max_v:.3f}V to {min_v:.3f}V (scale: {self.current_scale:.3f}V/div)")
                
            return max_v, min_v
                
        except Exception as e:
            tqdm.write(f"Measurement error: {e}")
            return 0.0, 0.0

    def get_full_waveform(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get complete waveform with time values"""
        if not self.scope:
            raise ConnectionError("Oscilloscope not connected")
            
        try:
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
