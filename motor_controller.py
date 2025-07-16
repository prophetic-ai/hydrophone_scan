"""
Motor Controller for Hydrophone Scanner
Handles Arduino communication for stepper motor control.
"""

import serial
import time
import logging
from typing import Dict, Optional
from tqdm import tqdm


class MotorController:

    def __init__(self, arduino_port: str, scope_address: Optional[str] = None, config: Optional[Dict] = None):
        self.arduino_port = arduino_port
        self.config = config
        self.arduino: Optional[serial.Serial] = None
        self.current_position: Dict[str, float] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        if self.config:
            self.MM_PER_STEP = {
                'x': 1 / self.config['hardware']['steps_per_mm']['x'],
                'y': 1 / self.config['hardware']['steps_per_mm']['y'],
                'z': 1 / self.config['hardware']['steps_per_mm']['z']
            }
        else:
            # Default values if no config provided
            self.MM_PER_STEP = {'x': 0.01, 'y': 0.01, 'z': 0.01}

        self._setup_connections()

    def _setup_connections(self) -> None:
        """Establish Arduino connection"""
        try:
            print("\nConnecting to Arduino...")
            print(f"Attempting to connect to port: {self.arduino_port}")
            self.arduino = serial.Serial(
                port=self.arduino_port,
                baudrate=115200,
                timeout=1
            )
            print(f"Serial port opened successfully: {self.arduino.is_open}")
            print("Waiting 2 seconds for Arduino to initialize...")
            time.sleep(2)

            # Try reading multiple times in case Arduino sends multiple lines
            print("Reading Arduino response...")
            response = self.arduino.readline().decode().strip()
            print(f"Arduino response: '{response}'")
            
            # If first response is empty, try reading a few more times
            if not response:
                print("First response empty, trying to read more...")
                for i in range(3):
                    time.sleep(0.5)
                    additional_response = self.arduino.readline().decode().strip()
                    print(f"Additional response {i+1}: '{additional_response}'")
                    if additional_response:
                        response = additional_response
                        break
            
            # Check if we have any data in the buffer
            bytes_waiting = self.arduino.in_waiting
            print(f"Bytes waiting in buffer: {bytes_waiting}")
            
            # Be more flexible with the response - check for "Arduino is ready" with any line endings
            if not response:
                print("\n" + "="*60)
                print("❌ NO ARDUINO FIRMWARE DETECTED")
                print("="*60)
                print("The Arduino is connected but not responding.")
                print("This means the firmware is not uploaded to the Arduino.")
                print("\nTo fix this:")
                print("1. Open Arduino IDE")
                print("2. Open the 'arduino.ino' file from this directory")
                print("3. Install AccelStepper library (Tools → Manage Libraries)")
                print("4. Select Board: Arduino Uno (Tools → Board)")
                print("5. Select Port: /dev/cu.usbmodem1401 (Tools → Port)")
                print("6. Upload the sketch (Ctrl+U)")
                print("="*60)
                raise ConnectionError("Arduino firmware not uploaded - see instructions above")
            elif "Arduino is ready" in response:
                print("✅ Arduino connected successfully")
            else:
                print(f"⚠️  Arduino responded but with unexpected message: '{response}'")
                print("Continuing anyway - this might still work...")

        except serial.SerialException as e:
            print(f"Serial connection error: {e}")
            raise ConnectionError(f"Failed to connect to Arduino: {e}")

    def move_axis(self, axis: str, distance: float) -> bool:
        """Move specified axis by given distance"""
        if axis not in self.MM_PER_STEP:
            raise ValueError(f"Invalid axis: {axis}")
        
        if not self.arduino:
            tqdm.write("Arduino not connected")
            return False

        try:
            # Enable motors before movement
            self.enable_motors()
            
            steps = round(distance / self.MM_PER_STEP[axis])
            direction = '+' if distance > 0 else '-'
            command = f"<{axis},{direction},{abs(steps)}>"
            self.arduino.write(command.encode())
            self.arduino.flush()
            
            # Wait for movement completion (Arduino will send response)
            response = self.arduino.readline().decode().strip()
            
            # Add position tracking
            self.current_position[axis] += distance
            
            # Disable motors after movement to reduce noise
            self.disable_motors()
            
            return True

        except serial.SerialException as e:
            tqdm.write(f"Movement error: {e}")
            return False

    def enable_motors(self) -> bool:
        """Enable stepper motors"""
        if not self.arduino:
            tqdm.write("Arduino not connected")
            return False
            
        try:
            command = "<e,+,0>"  # Enable command
            self.arduino.write(command.encode())
            self.arduino.flush()
            time.sleep(0.1)  # Small delay for motor enable
            return True
        except serial.SerialException as e:
            tqdm.write(f"Motor enable error: {e}")
            return False

    def disable_motors(self) -> bool:
        """Disable stepper motors to reduce noise"""
        if not self.arduino:
            tqdm.write("Arduino not connected")
            return False
            
        try:
            command = "<d,+,0>"  # Disable command
            self.arduino.write(command.encode())
            self.arduino.flush()
            time.sleep(0.1)  # Small delay for motor disable
            return True
        except serial.SerialException as e:
            tqdm.write(f"Motor disable error: {e}")
            return False

    def home_motors(self) -> bool:
        """Home all motors to center position"""
        if not self.arduino:
            tqdm.write("Arduino not connected")
            return False
            
        try:
            print("Homing motors...")
            command = "<h,+,0>"  # Home command
            self.arduino.write(command.encode())
            self.arduino.flush()
            
            # Wait for homing to complete - this can take a while
            # The Arduino will send a response when done
            response = self.arduino.readline().decode().strip()
            print(f"Homing complete: {response}")
            
            # Reset position tracking to center
            self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            
            return True
        except serial.SerialException as e:
            tqdm.write(f"Homing error: {e}")
            return False

    def move_to_position(self, target_position: Dict[str, float]) -> bool:
        """Move to absolute position"""
        current_pos = self.get_current_position()
        
        # Calculate required movements
        movements = {}
        for axis in ['x', 'y', 'z']:
            delta = target_position[axis] - current_pos[axis]
            if abs(delta) > 0.001:  # Only move if difference > 1 micron
                movements[axis] = delta
        
        # Execute movements
        for axis, delta in movements.items():
            if not self.move_axis(axis, delta):
                return False
        
        return True

    def get_current_position(self) -> Dict[str, float]:
        """Return the current position"""
        return self.current_position

    def close(self):
        """Close motor controller connections"""
        print("\nClosing motor controller connections...")
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
            print("Arduino disconnected")