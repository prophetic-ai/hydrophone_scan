# main.py
"""
Handles scan execution and user interaction with minimal complexity.
"""

import json
import time
from hardware import HardwareController
from scanner import ScanController
from processing import process_and_save_data

class HydrophoneScanner:
    def __init__(self):
        # Load configuration
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        
        # Initialize hardware
        self.hardware = HardwareController(
            arduino_port=self.config['hardware']['arduino_port'],
            scope_address=self.config['hardware']['scope_address']
        )
        
        self.scanner = ScanController(self.hardware)

    def manual_position_mode(self):
        """
        Interactive positioning mode:
        - Simple movement commands (x+, x-, y+, y-, z+, z-)
        - Basic amplitude feedback
        - Returns once user confirms position
        """
        while True:
            cmd = input("Move command (x+/x-/y+/y-/z+/z-/done): ")
            if cmd == 'done':
                break
            # Handle movement commands

    def execute_scan(self):
        """
        Core scan execution:
        1. Confirm start position
        2. Execute scan pattern
        3. Return to start
        """
        try:
            self.scanner.run_scan(
                scan_type=self.config['scan']['type'],
                dimensions=self.config['scan']['dimensions']
            )
            return True
        except Exception as e:
            print(f"Scan error: {e}")
            return False

def main():
    scanner = HydrophoneScanner()
    
    print("\n=== Hydrophone Scanner ===")
    print("Starting hardware initialization...")
    
    # Basic execution flow
    scanner.manual_position_mode()
    
    if input("\nReady to start scan? (y/n): ").lower() == 'y':
        print("\nStarting scan...")
        if scanner.execute_scan():
            print("Scan completed successfully")
        else:
            print("Scan failed")

if __name__ == "__main__":
    main()