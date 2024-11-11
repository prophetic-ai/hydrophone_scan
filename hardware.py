"""
Hardware control for Hydrophone Scanner
Handles Arduino and Oscilloscope communication.
"""

import serial
import time
import logging
from typing import Dict


class HardwareController:
    # Constants for hardware configuration
    MM_PER_STEP: Dict[str, float] = {
        'x': 0.01,
        'y': 0.01,
        'z': 0.01
    }
    
    def __init__(self, arduino_port: str, scope_address: str = None):
        """Initialize hardware connections"""
        self.arduino_port = arduino_port
        self.scope_address = scope_address
        self.arduino = None
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
            print(f"Sending command: {command}")  # Debug print
            self.arduino.write(command.encode())
                
            # Clear any existing data in the buffer
            self.arduino.flush()
                
            # The movement is successful if we were able to send the command
            # We don't need to verify the response since the Arduino is executing the movement
            return True
                
        except serial.SerialException as e:
            print(f"Movement error: {e}")
            return False



    def get_measurement(self):
        """Get single measurement from oscilloscope"""
        pass  # To be implemented in Step 2

    def close(self):
        """Close hardware connections"""
        if self.arduino and self.arduino.is_open:
            self.arduino.close()


def test_movement():
    """Interactive test function for movement control"""
    try:
        controller = HardwareController('/dev/tty.usbmodem101')
        
        print("\nHydrophone Movement Test")
        print("------------------------")
        print("Commands: x+/x-/y+/y-/z+/z- followed by distance in mm")
        print("Example: 'x+ 5' moves x axis 5mm positive")
        print("Enter 'q' to quit")
        
        while True:
            cmd = input("\nEnter command: ").lower().split()
            if not cmd:
                continue
                
            if cmd[0] == 'q':
                break
                
            if len(cmd) != 2:
                print("Invalid command format")
                continue
                
            direction, distance = cmd
            try:
                distance = float(distance)
                axis = direction[0]
                
                if direction[1] == '-':
                    distance = -distance
                    
                if controller.move_axis(axis, distance):
                    print(f"Moved {axis} axis by {distance}mm")
                    time.sleep(0.5)  # Add small delay between moves
                else:
                    print("Movement failed")
                    
            except (ValueError, IndexError):
                print("Invalid command format")
                
    except ConnectionError as e:
        print(f"Connection error: {e}")
    finally:
        if 'controller' in locals():
            controller.close()
        print("\nTest completed - connection closed")


if __name__ == "__main__":
    test_movement()