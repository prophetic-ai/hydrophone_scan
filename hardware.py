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
        
        self._setup_connections()

    def _setup_connections(self) -> None:
        """Establish hardware connections"""
        try:
            self.arduino = serial.Serial(
                port=self.arduino_port,
                baudrate=115200,
                timeout=1
            )
            time.sleep(2)
            
            response = self.arduino.readline().decode().strip()
            if not "Arduino is ready" in response:
                raise ConnectionError("Arduino not responding correctly")
                
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to Arduino: {e}")
        

        if self.scope_address:
            try:
                rm = pyvisa.ResourceManager()
                self.scope = rm.open_resource(self.scope_address)
                self.scope.timeout = 30000
                
                logging.info("Starting scope initialization...")
                
                # Reset and clear
                self.scope.write('*RST')
                time.sleep(2)
                self.scope.write('*CLS')
                time.sleep(1)
                
                # Verify basic communication
                idn = self.scope.query('*IDN?')
                logging.info(f"Connected to scope: {idn}")
                
                # Setup commands matching MATLAB exactly
                commands = [
                    # Channel setup
                    'CH1:COUPLING AC',
                    'CH1:SCALE 1.0',
                    'CH1:POSITION 0',
                    
                    # Trigger setup - matching MATLAB exactly
                    'TRIG:SOURCE EXT',
                    'TRIG:TYPE EDGE',
                    'TRIG:SLOPE RISing',
                    'TRIG:MODE AUTO',
                    'TRIG:COUPLING AC',  # Changed to AC coupling!
                    
                    # Data acquisition setup
                    'DATA:SOURCE CH1',
                    'DATA:WIDTH 1',
                    'DATA:ENCDG RIBINARY'
                ]
                
                for cmd in commands:
                    logging.info(f"Sending command: {cmd}")
                    self.scope.write(cmd)
                    time.sleep(0.5)
                
                # # Verify settings
                # try:
                #     coupling = self.scope.query('CH1:COUPLING?')
                #     logging.info(f"Channel coupling: {coupling.strip()}")
                    
                #     trig_coupling = self.scope.query('TRIG:COUPLING?')
                #     logging.info(f"Trigger coupling: {trig_coupling.strip()}")
                    
                #     scale = self.scope.query('CH1:SCALE?')
                #     logging.info(f"Vertical scale: {scale.strip()}")
                # except:
                #     logging.warning("Could not verify all settings, but continuing...")
                
            except Exception as e:
                logging.error(f"Scope setup error: {str(e)}")
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
            logging.error(f"Movement error: {e}")
            return False


    def get_measurement(self) -> Tuple[float, float]:
        """Get single measurement from scope with voltage-based scaling"""
        if not self.scope:
            raise ConnectionError("Oscilloscope not connected")
            
        try:
            # Start at 100mV/div
            current_scale = 0.1
            self.scope.write(f'CH1:SCALE {current_scale}')
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
            
            if peak_to_peak > 0.8 * current_scale * 8:  # Using >80% of display
                current_scale = min(1.0, current_scale * 2)  # Don't go above 1V/div
                logging.info(f"Signal too large, scale -> {current_scale:.3f}V/div")
                self.scope.write(f"CH1:Scale {current_scale}")
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
                
            elif peak_to_peak < 0.1 * current_scale * 8 and current_scale > 0.02:  # Using <10% of display
                current_scale = max(0.02, current_scale * 0.5)  # Don't go below 20mV/div
                logging.info(f"Signal too small, scale -> {current_scale:.3f}V/div")
                self.scope.write(f"CH1:Scale {current_scale}")
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
            
            logging.info(f"Final measurement: {max_v:.3f}V to {min_v:.3f}V (scale: {current_scale:.3f}V/div)")
            return max_v, min_v
                
        except Exception as e:
            logging.error(f"Measurement error: {e}")
            return 0.0, 0.0


    def get_full_waveform(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get complete waveform with time values"""
        if not self.scope:
            raise ConnectionError("Oscilloscope not connected")
            
        try:
            # Get data same as get_measurement
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
            logging.error(f"Waveform acquisition error: {e}")
            return None, None

    def close(self):
        """Close hardware connections"""
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        if self.scope:
            self.scope.close()

