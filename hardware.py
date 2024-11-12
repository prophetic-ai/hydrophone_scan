"""
Hardware control for Hydrophone Scanner
Handles Arduino and Oscilloscope communication.
"""

import serial
import time
import logging
from typing import Dict
import pyvisa
import numpy as np

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
        self._setup_connections()

    def _setup_connections(self) -> None:
        """Establish hardware connections"""
        try:
            self.arduino = serial.Serial(
                port=self.arduino_port,
                baudrate=115200,
                timeout=1
            )
            time.sleep(2)  # Wait for Arduino to initialize
            
            # Verify Arduino is responding
            response = self.arduino.readline().decode().strip()
            if not "Arduino is ready" in response:
                raise ConnectionError("Arduino not responding correctly")
                
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to connect to Arduino: {e}")
        
        # Scope setup
        # if self.scope_address:
        #     try:
        #         rm = pyvisa.ResourceManager()
        #         self.scope = rm.open_resource(self.scope_address)
        #         self.scope.timeout = 10000  # 10 seconds timeout
                
        #         # Basic scope setup
        #         self.scope.write('*RST')  # Reset scope
        #         self.scope.write('DATA:SOURCE CH1')  # Set channel 1 as source
        #         self.scope.write('DATA:WIDTH 1')  # Set data width
        #         self.scope.write('DATA:ENC RPB')  # Set encoding to positive binary
                
        #     except Exception as e:
        #         raise ConnectionError(f"Failed to connect to oscilloscope: {e}")

        if self.scope_address:
            try:
                rm = pyvisa.ResourceManager()
                self.scope = rm.open_resource(self.scope_address)
                self.scope.timeout = 10000  # 10 seconds timeout
                
                # Configure scope with optimal settings
                self.scope.write('*RST')  # Reset first
                self.scope.write('TRIG:SOURCE EXT')  # External trigger source
                self.scope.write('TRIG:TYPE EDGE')   # Edge trigger type
                self.scope.write('TRIG:SLOPE RISing')  # Rising edge
                self.scope.write('TRIG:MODE AUTO')  # Auto trigger mode
                self.scope.write('TRIG:COUPLING DC')  # DC coupling for trigger
                self.scope.write('CH1:SCALE 0.05')  # 50mV vertical scale
                self.scope.write('DATA:SOURCE CH1')  # Set channel 1 as source
                self.scope.write('DATA:WIDTH 1')     # Set data width
                self.scope.write('DATA:ENC RPB')     # Set encoding to positive binary
                
            except Exception as e:
                raise ConnectionError(f"Failed to connect to oscilloscope: {e}")

    def move_axis(self, axis: str, distance: float) -> bool:
        """Move specified axis by given distance"""
        if axis not in self.MM_PER_STEP:
            raise ValueError(f"Invalid axis: {axis}")
                
        try:
            # Convert distance to steps
            steps = round(distance / self.MM_PER_STEP[axis])
            direction = '+' if distance > 0 else '-'
                
            # Send movement command
            command = f"<{axis},{direction},{abs(steps)}>"
            self.arduino.write(command.encode())
                
            # Clear any existing data in the buffer
            self.arduino.flush()

            return True
                
        except serial.SerialException as e:
            print(f"Movement error: {e}")
            return False

    def get_measurement(self) -> tuple[float, float]:
        """Get single measurement from scope with MATLAB-like vertical scaling"""
        if not self.scope:
            raise ConnectionError("Oscilloscope not connected")
            
        try:
            # Clear oscilloscope status
            self.scope.write('*CLS')
            
            # Get waveform
            self.scope.write('CURVE?')
            raw_wave = self.scope.query_binary_values('CURVE?', datatype='b', container=np.array)
            
            # Get current settings
            volts_per_div = float(self.scope.query("CH1:Scale?"))
            y_offset = float(self.scope.query("WFMPRe:YOFf?"))
            
            # Calculate raw min/max
            raw_max = np.max(raw_wave)
            raw_min = np.min(raw_wave)
            
            # MATLAB-like scaling thresholds
            UPPER_LIMIT = 90
            LOWER_LIMIT = 20
            ROUND_BIN = 20e-3  # 20mV
            
            # Check if scaling needed
            scaling_needed = (raw_max > UPPER_LIMIT or raw_max < LOWER_LIMIT or 
                            abs(raw_min) > UPPER_LIMIT or abs(raw_min) < LOWER_LIMIT)
            
            if scaling_needed and volts_per_div > ROUND_BIN:
                raw_scaler = np.mean([raw_max, abs(raw_min)])
                if raw_max > UPPER_LIMIT or abs(raw_min) > UPPER_LIMIT:
                    new_scale = volts_per_div * raw_scaler / UPPER_LIMIT
                    new_scale = np.ceil(new_scale / ROUND_BIN) * ROUND_BIN
                else:
                    new_scale = volts_per_div * raw_scaler / LOWER_LIMIT
                    new_scale = np.floor(new_scale / ROUND_BIN) * ROUND_BIN
                
                self.scope.write(f'CH1:Scale {new_scale}')
                time.sleep(0.2)  # Let scope settle
                return self.get_measurement()  # Recursive call with new scale
            
            # Get measurements
            self.scope.write('MEASUREMENT:IMMED:TYPE PK2PK')
            pk2pk = float(self.scope.query('MEASUREMENT:IMMED:VALUE?'))
            
            self.scope.write('MEASUREMENT:IMMED:TYPE MINIMUM')
            min_val = float(self.scope.query('MEASUREMENT:IMMED:VALUE?'))
            
            return (min_val + pk2pk, min_val)
            
        except Exception as e:
            logging.error(f"Measurement error: {e}")
            return (0.0, 0.0)

    def close(self):
        """Close hardware connections"""
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
        if self.scope:
            self.scope.close()


# def test_all():
#     """Test both movement and measurements"""
#     try:
#         controller = HardwareController(
#             arduino_port='/dev/tty.usbmodem1101',
#             scope_address='USB0::0x0699::0x03A0::C014274::INSTR'
#         )
        
#         print("\nHydrophone Test System")
#         print("---------------------")
#         print("Commands:")
#         print("  move x+/x-/y+/y-/z+/z- <distance>  - Move axis by distance in mm")
#         print("  measure                             - Take scope measurement")
#         print("  q                                   - Quit")
        
#         while True:
#             cmd = input("\nEnter command: ").lower().split()
#             if not cmd:
#                 continue
                
#             if cmd[0] == 'q':
#                 break
                
#             if cmd[0] == 'measure':
#                 pos_peak, neg_peak = controller.get_measurement()
#                 print(f"Measurement: Positive peak: {pos_peak:.3f}V, Negative peak: {neg_peak:.3f}V")
#                 continue
                
#             if cmd[0] == 'move' and len(cmd) == 3:
#                 direction = cmd[1]
#                 distance = float(cmd[2])
#                 axis = direction[0]
                
#                 if direction[1] == '-':
#                     distance = -distance
                    
#                 if controller.move_axis(axis, distance):
#                     print(f"Moved {axis} axis by {distance}mm")
#                     time.sleep(0.5)
#                 else:
#                     print("Movement failed")
#             else:
#                 print("Invalid command")
                
#     except ConnectionError as e:
#         print(f"Connection error: {e}")
#     finally:
#         if 'controller' in locals():
#             controller.close()
#         print("\nTest completed - connections closed")

# if __name__ == "__main__":
#     test_all()