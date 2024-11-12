"""
Main execution script for Hydrophone Scanner
Handles scan execution and user interaction
"""

import logging
from hardware import HardwareController
from scanner import ScanController
from processing import DataProcessor
from config import load_config
from datetime import datetime
import sys

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class HydrophoneScanner:
    def __init__(self):
        """Initialize scanner with configuration"""
        try:
            self.config = load_config('config.yaml')
            
            self.hardware = HardwareController(
                arduino_port=self.config['hardware']['arduino_port'],
                scope_address=self.config['hardware']['scope_address']
            )
            
            self.processor = DataProcessor(self.config)
            # Pass processor to scanner for visualization
            self.scanner = ScanController(self.hardware, self.processor)
            
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise

    def manual_position_mode(self):
        """Interactive positioning mode"""
        print("\nManual Positioning Mode")
        print("----------------------")
        print("Commands:")
        print("  x+/x-/y+/y-/z+/z- <distance>  - Move axis by distance in mm")
        print("  m                              - Measure current position")
        print("  done                           - Finish positioning")
        
        while True:
            try:
                cmd = input("\nEnter command: ").lower().split()
                if not cmd:
                    continue
                    
                if cmd[0] == 'done':
                    break
                    
                if cmd[0] == 'm':
                    pos_peak, neg_peak = self.hardware.get_measurement()
                    print(f"Measurement: +{pos_peak:.3f}V, {neg_peak:.3f}V")
                    continue
                    
                if len(cmd) == 2 and cmd[0][0] in 'xyz' and cmd[0][1] in '+-':
                    distance = float(cmd[1])
                    axis = cmd[0][0]
                    if cmd[0][1] == '-':
                        distance = -distance
                        
                    if self.hardware.move_axis(axis, distance):
                        print(f"Moved {axis} axis by {distance}mm")
                    else:
                        print("Movement failed")
                else:
                    print("Invalid command")
                    
            except Exception as e:
                print(f"Error: {e}")

    def execute_scan(self):
        """Execute complete scan workflow"""
        try:
            print("\nStarting scan...")
            scan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Execute scan and collect data
            data = self.scanner.run_scan(
                scan_type=self.config['scan']['type'],
                dimensions=self.config['scan']['dimensions']
            )
            
            # Process and save results
            self.processor.process_and_save(data, scan_id)
            
            print("\nScan completed successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Scan error: {e}")
            return False

    def close(self):
        """Clean up hardware connections"""
        self.hardware.close()

def main():
    scanner = None
    try:
        scanner = HydrophoneScanner()
        
        print("\n=== Hydrophone Scanner ===")
        print("Starting hardware initialization...")
        
        scanner.manual_position_mode()
        
        if input("\nReady to start scan? (y/n): ").lower() == 'y':
            scanner.execute_scan()
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        if scanner:
            scanner.close()
        print("\nScanner shutdown complete")

if __name__ == "__main__":
    main()