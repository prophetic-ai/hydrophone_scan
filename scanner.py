"""
Core scanning logic
Handles scan patterns, data acquisition
"""

import time
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from tqdm import tqdm

class ScanController:
    def __init__(self, hardware, processor=None):
        self.hardware = hardware
        self.processor = processor
        self.data = []
        self.start_position = None
        self.current_position = {'x': 0, 'y': 0, 'z': 0}
        self.progress_bar = None

    def _record_start_position(self) -> None:
        """Record the starting position for return after scan"""
        self.start_position = self.current_position.copy()
        logging.info(f"Recorded start position: {self.start_position}")

    def _move_relative(self, axis: str, distance: float) -> bool:
        """Move relative to current position and update tracking"""
        success = self.hardware.move_axis(axis, distance)
        if success:
            self.current_position[axis] += distance
        return success
    
    def _return_to_start(self) -> None:
        """Return to the recorded start position"""
        if not self.start_position:
            logging.warning("No start position recorded")
            return

        for axis in ['x', 'y', 'z']:
            distance = self.start_position[axis] - self.current_position[axis]
            if abs(distance) > 0.001:  # Only move if significant distance
                self._move_relative(axis, distance)
                time.sleep(0.1)
    
    def _collect_datapoint(self) -> Tuple[float, float]:
        """Collect a single datapoint"""
        return self.hardware.get_measurement()

    def run_scan(self, scan_type, dimensions):
        """Execute scan pattern and collect data"""
        self.data = []
        self._record_start_position()
        
        # Calculate total points
        if scan_type.startswith('1d'):
            axis = scan_type[-1]
            total_points = int(dimensions[axis] / dimensions['resolution'])
        else:
            axes = scan_type[-2:]
            total_points = (
                int(dimensions[axes[0]] / dimensions['resolution']) *
                int(dimensions[axes[1]] / dimensions['resolution'])
            )
        
        try:
            self.progress_bar = tqdm(
                total=total_points, 
                desc=f"Scanning {scan_type}",
                ncols=80,
                unit="pts"
            )
            
            if scan_type.startswith('1d'):
                self._run_1d_scan(scan_type[-1], dimensions)
            else:
                self._run_2d_scan(scan_type[-2:], dimensions)
                
        except Exception as e:
            logging.error(f"Scan error: {e}")
            raise
        except KeyboardInterrupt:
            logging.info("Scan cancelled by user")
            raise
        finally:
            if self.progress_bar:
                self.progress_bar.close()
            self._return_to_start()
            
        return self.data

    def _run_1d_scan(self, axis: str, dimensions: Dict) -> None:
        """Execute 1D scan along specified axis"""
        distance = dimensions[axis]
        step_size = dimensions['resolution']
        steps = int(distance / step_size)
        
        # Move to start position
        start_offset = -distance / 2
        self._move_relative(axis, start_offset)
        time.sleep(0.2)
        
        # Execute scan
        for i in range(steps):
            pos_peak, neg_peak = self._collect_datapoint()
            position = self.current_position.copy()
            self.data.append({
                'position': position,
                'peaks': (pos_peak, neg_peak)
            })
            
            self.progress_bar.update(1)
            
            if i < steps - 1:
                self._move_relative(axis, step_size)
                time.sleep(0.1)

    def _run_2d_scan(self, axes: str, dimensions: Dict) -> None:
        """Execute 2D scan in specified plane"""
        primary_axis = axes[0]
        secondary_axis = axes[1]
        
        primary_steps = int(dimensions[primary_axis] / dimensions['resolution'])
        secondary_steps = int(dimensions[secondary_axis] / dimensions['resolution'])
        
        # Move to start position
        self._move_relative(primary_axis, -dimensions[primary_axis] / 2)
        self._move_relative(secondary_axis, -dimensions[secondary_axis] / 2)
        time.sleep(0.2)
        
        scan_index = 0
        
        # Execute serpentine scan pattern
        for j in range(secondary_steps):
            direction = 1 if j % 2 == 0 else -1
            
            for i in range(primary_steps):
                pos_peak, neg_peak = self._collect_datapoint()
                position = self.current_position.copy()
                self.data.append({
                    'position': position,
                    'peaks': (pos_peak, neg_peak)
                })
                
                self.progress_bar.update(1)
                scan_index += 1
                
                if i < primary_steps - 1:
                    self._move_relative(primary_axis, direction * dimensions['resolution'])
                    time.sleep(0.1)
            
            if j < secondary_steps - 1:
                self._move_relative(secondary_axis, dimensions['resolution'])
                time.sleep(0.1)


# def test_all():
#     """
#     Test basic scanner functionality interactively
#     """
#     from hardware import HardwareController
    
#     try:
#         print("\nScanner Test System")
#         print("------------------")
        
#         # Initialize hardware with your port/address
#         hardware = HardwareController(
#             arduino_port='/dev/tty.usbmodem101',
#             scope_address='USB0::0x0699::0x03A0::C014274::INSTR'
#         )
        
#         scanner = ScanController(hardware)
        
#         while True:
#             print("\nTest Commands:")
#             print("1. Test 1D X scan")
#             print("2. Test 1D Y scan")
#             print("3. Test 1D Z scan")
#             print("4. Test 2D XY scan")
#             print("5. Test 2D XZ scan")
#             print("6. Test 2D YZ scan")
#             print("q. Quit")
            
#             cmd = input("\nEnter command: ").lower()
            
#             if cmd == 'q':
#                 break
                
#             try:
#                 if cmd == '1':
#                     print("\nRunning 1D X scan...")
#                     data = scanner.run_scan('1d_x', {
#                         'range': 10,  # 10mm range
#                         'resolution': 0.5  # 0.5mm steps
#                     })
#                     print(f"Collected {len(data)} points")
                    
#                 elif cmd == '2':
#                     print("\nRunning 1D Y scan...")
#                     data = scanner.run_scan('1d_y', {
#                         'range': 10,
#                         'resolution': 0.5
#                     })
#                     print(f"Collected {len(data)} points")
                    
#                 elif cmd == '3':
#                     print("\nRunning 1D Z scan...")
#                     data = scanner.run_scan('1d_z', {
#                         'range': 10,
#                         'resolution': 0.5
#                     })
#                     print(f"Collected {len(data)} points")
                    
#                 elif cmd == '4':
#                     print("\nRunning 2D XY scan...")
#                     data = scanner.run_scan('2d_xy', {
#                         'x_range': 10,
#                         'y_range': 10,
#                         'resolution': 0.5
#                     })
#                     print(f"Collected {len(data)} points")
                    
#                 elif cmd == '5':
#                     print("\nRunning 2D XZ scan...")
#                     data = scanner.run_scan('2d_xz', {
#                         'x_range': 10,
#                         'z_range': 10,
#                         'resolution': 0.5
#                     })
#                     print(f"Collected {len(data)} points")
                    
#                 elif cmd == '6':
#                     print("\nRunning 2D YZ scan...")
#                     data = scanner.run_scan('2d_yz', {
#                         'y_range': 2,
#                         'z_range': 2,
#                         'resolution': 0.5
#                     })
#                     print(f"Collected {len(data)} points")
                
#                 # Print last few data points
#                 if len(data) > 0:
#                     print("\nLast few measurements:")
#                     for point in data[-3:]:
#                         print(f"Position: {point['position']}")
#                         print(f"Peaks: {point['peaks']}")
                        
#             except Exception as e:
#                 print(f"Test failed: {e}")
                
#     finally:
#         if 'hardware' in locals():
#             hardware.close()
#         print("\nTest completed")

# if __name__ == "__main__":
#     test_all()