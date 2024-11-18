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
import os
import yaml
import numpy as np
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')



class HydrophoneScanner:
    def __init__(self):
        """Initialize scanner with configuration"""
        try:
            self.config = load_config('config.yaml')
            self.latest_scan_path = None
            
            self.hardware = HardwareController(
                arduino_port=self.config['hardware']['arduino_port'],
                scope_address=self.config['hardware']['scope_address'],
                config=self.config
            )
            
            self.scanner = ScanController(self.hardware)
            self.processor = DataProcessor(self.config)
            
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise
    

    def reload_config(self):
        """Reload configuration from file"""
        self.config = load_config('config.yaml')
        # Update dependent components with new config
        self.scanner = ScanController(self.hardware) 
        self.processor = DataProcessor(self.config)
        print("\nConfiguration reloaded from config.yaml")


    def get_latest_scan_path(self):
        """Return path to latest scan"""
        return self.latest_scan_path
    

    def update_scan_center(self, current_position):
        """Update scan center based on current position and save new config"""
        # Store the original dimension sizes
        original_dimensions = {
            'x': self.config['scan']['dimensions']['x'],
            'y': self.config['scan']['dimensions']['y'],
            'z': self.config['scan']['dimensions']['z'],
            'resolution': self.config['scan']['dimensions']['resolution']
        }
        
        # Update the scan center (offset) while preserving dimensions
        self.config['scan']['dimensions'] = {
            # Keep original sizes for the scan dimensions
            'x': original_dimensions['x'],
            'y': original_dimensions['y'],
            'z': original_dimensions['z'],
            'resolution': original_dimensions['resolution'],
            # Add center position
            'center_x': current_position['x'],
            'center_y': current_position['y'],
            'center_z': current_position['z']
        }
        
        # Save updated config
        config_path = os.path.join(
            self.latest_scan_path, 
            f'config_{datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml'
        )
        
        with open(config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
            
        print(f"\nSaved updated config to: {config_path}")


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
            scan_path = os.path.join(self.config['scan']['base_path'], scan_id)
            self.processor.process_and_save(data, scan_id)
            
            # Store latest scan path
            self.latest_scan_path = scan_path
            
            print("\nScan completed successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Scan error: {e}")
            return False





    def manual_position_mode(self):
        """Interactive positioning mode"""
        print("\nManual Positioning Mode")
        print("----------------------")
        print("Commands:")
        print("  x+/x-/y+/y-/z+/z- <distance>  - Move axis by distance in mm")
        print("  m                              - Measure current position")
        print("  w                              - View current waveform")
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
                    
                if cmd[0] == 'w':
                    # Switch to TkAgg only when plotting
                    import matplotlib
                    current_backend = matplotlib.get_backend()
                    matplotlib.use('TkAgg')
                    import matplotlib.pyplot as plt
                    
                    time_array, voltage_array = self.hardware.get_full_waveform()
                    if time_array is not None and voltage_array is not None:
                        plt.figure(figsize=(10, 6))
                        plt.plot(time_array * 1e6, voltage_array, 'b-', linewidth=1)
                        plt.title('Current Waveform')
                        plt.xlabel('Time (μs)')
                        plt.ylabel('Voltage (V)')
                        plt.grid(True)
                        
                        max_idx = np.argmax(voltage_array)
                        min_idx = np.argmin(voltage_array)
                        plt.plot(time_array[max_idx] * 1e6, voltage_array[max_idx], 'r^', 
                                label=f'+{voltage_array[max_idx]:.3f}V')
                        plt.plot(time_array[min_idx] * 1e6, voltage_array[min_idx], 'rv', 
                                label=f'{voltage_array[min_idx]:.3f}V')
                        plt.legend()
                        
                        plt.show(block=False)
                        print(f"Peak values: +{voltage_array[max_idx]:.3f}V, {voltage_array[min_idx]:.3f}V")
                    else:
                        print("Failed to acquire waveform")
                    
                    # Switch back to original backend
                    matplotlib.use(current_backend)
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



    def close(self):
        """Clean up hardware connections"""
        self.hardware.close()



def main():
    scanner = None
    try:
        # Import and configure matplotlib
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        
        scanner = HydrophoneScanner()
        
        print("\n=== Hydrophone Scanner ===")
        print("Starting hardware initialization...")
        
        while True:  # Main program loop
            # Close any existing plots before showing menu
            plt.close('all')
            
            # Unified positioning and config step
            print("\nBefore scanning:")
            print("1. Enter positioning mode")
            print("2. Reload config")
            print("3. Start scan")
            print("4. Exit")
            
            choice = input("Choice: ")
            
            if choice == '1':
                scanner.manual_position_mode()
                continue
            elif choice == '2':
                scanner.reload_config()
                continue
            elif choice == '3':
                if input("\nReady to start scan? (y/n): ").lower() != 'y':
                    continue
            elif choice == '4':
                break
            else:
                print("Invalid choice")
                continue
            
            # Execute scan
            scan_successful = scanner.execute_scan()
            
            if scan_successful:
                latest_scan_path = scanner.get_latest_scan_path()
                if latest_scan_path:
                    print("\nScan Results:")
                    print(f"Pressure maps saved to: {os.path.join(latest_scan_path, 'pressure_maps.png')}")
                    
                    # Single prompt for next action
                    print("\nWhat would you like to do next?")
                    print("1. Run another scan")
                    print("2. Adjust position and scan again")
                    print("3. Exit")
                    
                    next_action = input("Choice: ")
                    
                    if next_action == '1':
                        continue
                    elif next_action == '2':
                        scanner.manual_position_mode()
                        current_pos = scanner.hardware.get_current_position()
                        scanner.update_scan_center(current_pos)
                        continue
                    else:
                        break
                    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        if scanner:
            scanner.close()
        plt.close('all')  # Make sure all plots are closed on exit
        print("\nScanner shutdown complete")




if __name__ == "__main__":
    main()