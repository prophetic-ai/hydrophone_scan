"""
Motor Controller for Hydrophone Scanner
Handles Arduino communication for stepper motor control.
"""

import serial
import time
from typing import Dict, Optional
from tqdm import tqdm
from datetime import datetime
from pathlib import Path

class MotorController:

    def __init__(self, arduino_port: str, scope_address: Optional[str] = None, config: Optional[Dict] = None):
        self.arduino_port = arduino_port
        self.config = config
        self.arduino: Optional[serial.Serial] = None
        self.current_position: Dict[str, float] = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        # Logging setup - will be initialized when scan starts
        self.log_file = None
        self.logging_enabled = False
        
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

    def start_scan_logging(self, scan_dir: Path):
        """Start logging to file in the scan directory"""
        # Create log file in scan directory
        self.log_file = scan_dir / 'motor_controller.log'
        self.logging_enabled = True
        
        # Write initial log entry
        initial_message = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Motor controller scan logging started - Log file: {self.log_file}"
        with open(self.log_file, 'w') as f:  # Use 'w' to create new file
            f.write(initial_message + '\n')
            f.flush()
        print(f"📝 Motor logging started: {self.log_file}")

    def stop_scan_logging(self):
        """Stop logging to file"""
        if self.logging_enabled and self.log_file:
            self._log_and_print("Motor controller scan logging ended")
            print(f"📝 Motor logging saved: {self.log_file}")
        self.logging_enabled = False
        self.log_file = None

    def _setup_logging(self):
        """Setup logging to file with timestamps - REMOVED, now handled by start_scan_logging"""
        pass

    def _log_and_print(self, message: str):
        """Log message to both file and console with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
        formatted_message = f"[{timestamp}] {message}"
        
        # Write to log file only if logging is enabled
        if self.logging_enabled and self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(formatted_message + '\n')
                    f.flush()  # Ensure immediate write
            except Exception as e:
                print(f"Logging error: {e}")
        
        # Also print to console
        tqdm.write(formatted_message)

    def _format_position(self, position: Dict[str, float]) -> Dict[str, float]:
        """Convert numpy types to regular floats for cleaner logging"""
        return {axis: float(pos) for axis, pos in position.items()}

    def _setup_connections(self) -> None:
        """Establish Arduino connection"""
        try:
            print("Connecting to Arduino...")
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
                print("="*60)
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
                # Ensure motors remain disabled by default on connect
                self.disable_motors()
                print("✅ Arduino connected successfully (motors disabled)")
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
            self._log_and_print("Arduino not connected")
            return False

        try:
            # Enable motors before movement
            self.enable_motors()
            
            steps = round(distance / self.MM_PER_STEP[axis])
            direction = '+' if distance > 0 else '-'
            command = f"<{axis},{direction},{abs(steps)}>"
            
            # Debug logging
            self._log_and_print(f"Sending command: {command} (distance: {distance:+.3f}mm)")
            
            # Clear any buffered data before sending command
            if self.arduino.in_waiting > 0:
                buffered_data = self.arduino.read_all().decode('utf-8', errors='ignore')
                self._log_and_print(f"Cleared buffer before command: '{buffered_data}'")
            
            self.arduino.write(command.encode())
            self.arduino.flush()
            
            # Wait for movement completion (Arduino will send response)
            try:
                # Give Arduino time to process and respond
                time.sleep(0.1)
                
                response = self.arduino.readline().decode().strip()
                self._log_and_print(f"Arduino response: '{response}'")
                
                # Check if response matches expected format (axis + direction + steps)
                expected_response = f"{axis}{direction}{abs(steps)}"
                if response != expected_response:
                    self._log_and_print(f"⚠️  Unexpected response! Expected: '{expected_response}', Got: '{response}'")
                
                # Check if response indicates an error or limit switch hit
                if "limit" in response.lower() or "reached" in response.lower():
                    self._log_and_print(f"⚠️  Limit switch detected during movement!")
                    # Don't update position tracking if limit was hit
                    # self.disable_motors()
                    return False
                    
            except Exception as e:
                self._log_and_print(f"Communication error: {e}")
                self.disable_motors()
                return False
            
            # Add position tracking
            old_position = self.current_position[axis]
            self.current_position[axis] += distance
            self._log_and_print(f"Position updated: {axis} {old_position:.3f} → {self.current_position[axis]:.3f}mm")
            
            # Disable motors after movement to reduce noise
            self.disable_motors()
            
            return True

        except serial.SerialException as e:
            self._log_and_print(f"Movement error: {e}")
            return False

    def enable_motors(self) -> bool:
        """Enable stepper motors"""
        if not self.arduino:
            self._log_and_print("Arduino not connected")
            return False
            
        try:
            command = "<e,+,0>"  # Enable command
            self.arduino.write(command.encode())
            self.arduino.flush()
            time.sleep(0.1)  # Small delay for motor enable
            
            # Clear the response to avoid interference with movement commands
            if self.arduino.in_waiting > 0:
                response = self.arduino.read_all().decode('utf-8', errors='ignore').strip()
                self._log_and_print(f"Motor enable response: '{response}'")
            
            return True
        except serial.SerialException as e:
            self._log_and_print(f"Motor enable error: {e}")
            return False

    def disable_motors(self) -> bool:
        """Disable stepper motors to reduce noise"""
        if not self.arduino:
            self._log_and_print("Arduino not connected")
            return False
            
        try:
            command = "<d,+,0>"  # Disable command
            self.arduino.write(command.encode())
            self.arduino.flush()
            time.sleep(0.1)  # Small delay for motor disable
            
            # Clear the response to avoid interference with movement commands
            if self.arduino.in_waiting > 0:
                response = self.arduino.read_all().decode('utf-8', errors='ignore').strip()
                self._log_and_print(f"Motor disable response: '{response}'")
            
            return True
        except serial.SerialException as e:
            self._log_and_print(f"Motor disable error: {e}")
            return False

    def home_motors(self) -> bool:
        """Home all motors to center position"""
        if not self.arduino:
            self._log_and_print("Arduino not connected")
            return False
            
        try:
            self._log_and_print("Homing motors...")
            command = "<h,+,0>"  # Home command
            self.arduino.write(command.encode())
            self.arduino.flush()
            
            # Wait for homing to complete - this can take a while
            # The Arduino will send a response when done
            response = self.arduino.readline().decode().strip()
            self._log_and_print(f"Homing complete: {response}")
            
            # Reset position tracking to center
            self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            
            return True
        except serial.SerialException as e:
            self._log_and_print(f"Homing error: {e}")
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
        
        # Log the movement plan (clean up numpy types) - current position first
        if movements:
            self._log_and_print(f"Current position: {self._format_position(current_pos)}")
            self._log_and_print(f"Moving to position: {self._format_position(target_position)}")
            self._log_and_print(f"Required movements: {self._format_position(movements)}")
        
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
        print("Closing motor controller connections...")
        if self.arduino and self.arduino.is_open:
            self.arduino.close()
            print("Arduino disconnected")