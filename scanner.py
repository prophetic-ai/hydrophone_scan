"""
Core scanning logic
Handles scan patterns, data acquisition (scope scaling)
"""

import time
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from tqdm import tqdm

class ScanController:
    def __init__(self, hardware):
        self.hardware = hardware
        self.data = []
        self.start_position = None
        self.current_position = {'x': 0, 'y': 0, 'z': 0}

        # Scaling parameters
        self.upper_limit = 90  # Upper digitizer level limit
        self.lower_limit = 20  # Lower digitizer level limit
        self.rounding_bin = 0.02  # Voltage rounding bin (20mV)

    def _record_start_position(self) -> None:
        """Record the starting position for return after scan"""
        self.start_position = self.current_position.copy()
        tqdm.write(f"Recorded start position: {self.start_position}")

    def _move_relative(self, axis: str, distance: float) -> bool:
        """Move relative to current position and update tracking"""
        success = self.hardware.move_axis(axis, distance)
        if success:
            self.current_position[axis] += distance
        return success
    
    def _return_to_start(self) -> None:
        """Return to the recorded start position"""
        if not self.start_position:
            tqdm.write("Warning: No start position recorded")
            return

        print("\nReturning to start position...")
        for axis in ['x', 'y', 'z']:
            distance = self.start_position[axis] - self.current_position[axis]
            if distance != 0:
                self._move_relative(axis, distance)
                time.sleep(0.1)  # Small delay between movements
    
    def _collect_datapoint(self) -> Tuple[float, float]:
        """
        Collect peaks & waveform data for a current position
        """

        peaks = self.hardware.get_measurement()
        time_array, voltage_array = self.hardware.get_full_waveform()
        
        return {
            'position': self.current_position.copy(),
            'peaks': peaks,
            'waveform': {
            'time': time_array.tolist() if time_array is not None else None,
            'voltage': voltage_array.tolist() if voltage_array is not None else None
            }
        } 

    def run_scan(self, scan_type, dimensions):
        """
        Execute scan pattern and collect data
        
        Args:
            scan_type: '1d_x', '1d_y', '1d_z', '2d_xy', '2d_xz', '2d_yz'
            dimensions: dict with scan dimensions and resolution
            
        Returns:
            List of scan data points
        """
        self.data = []
        self._record_start_position()
        
        try:
            if scan_type.startswith('1d'):
                self._run_1d_scan(scan_type[-1], dimensions)
            else:
                self._run_2d_scan(scan_type[-2:], dimensions)
                
        except Exception as e:
            tqdm.write(f"\nScan error: {e}")
            raise
            
        finally:
            self._return_to_start()
            
        return self.data

    def _run_1d_scan(self, axis: str, dimensions: Dict) -> None:
        """
        Execute 1D scan along specified axis
        """
        distance = dimensions[axis]
        step_size = dimensions['resolution']
        steps = int(distance / step_size)
        
        # Move to start position
        print(f"\nMoving to scan start position...")
        start_offset = -distance / 2
        self._move_relative(axis, start_offset)
        
        time.sleep(1)
        
        for _ in range(3):
            self.hardware.get_measurement()
            time.sleep(0.2)
        
        # Execute scan with progress bar
        print(f"\nStarting {axis}-axis scan ({steps} points)...")
        with tqdm(total=steps, desc=f"Scanning {axis}-axis", 
                bar_format='{desc}: {percentage:3.1f}%|{bar:50}| {n_fmt}/{total_fmt} pts [{elapsed}<{remaining}]',
                ascii=False, ncols=120, leave=True) as pbar:
            
            for i in range(steps):
                # Collect data - now includes waveform
                point_data = self._collect_datapoint()
                self.data.append(point_data)  # Add complete point data
                
                # Move to next position if not at end
                if i < steps - 1:
                    self._move_relative(axis, step_size)
                    time.sleep(0.1)
                
                pbar.update(1)


    def _run_2d_scan(self, axes: str, dimensions: Dict) -> None:
        """
        Execute 2D scan in specified plane with a clean progress bar
        """
        # Calculate steps
        primary_axis = axes[0]
        secondary_axis = axes[1]
        
        primary_steps = int(dimensions[primary_axis] / dimensions['resolution'])
        secondary_steps = int(dimensions[secondary_axis] / dimensions['resolution'])
        total_points = primary_steps * secondary_steps
        
        # Move to start position
        print(f"\nMoving to scan start position...")
        self._move_relative(primary_axis, -dimensions[primary_axis] / 2)
        self._move_relative(secondary_axis, -dimensions[secondary_axis] / 2)
        time.sleep(1)
            
        for _ in range(3):
            self.hardware.get_measurement()
            time.sleep(0.2)
        
        # Execute serpentine scan pattern with a single progress bar
        print(f"\nStarting {axes}-plane scan ({total_points} points)")
        
        # Create progress bar that will stay on one line
        pbar = tqdm(total=total_points,
                    desc=f"Scanning {axes}-plane",
                    bar_format='{desc} |{bar:50}| {percentage:3.0f}% [{n_fmt}/{total_fmt}] Row {postfix}',
                    ncols=100)
        
        try:
            for j in range(secondary_steps):
                pbar.set_postfix_str(f"{j+1}/{secondary_steps}")
                
                # Determine primary axis direction for this row
                direction = 1 if j % 2 == 0 else -1
                
                # Scan along primary axis
                for i in range(primary_steps):
                    # Collect data
                    point_data = self._collect_datapoint()
                    self.data.append(point_data)
                    
                    # Move to next position if not at end of line
                    if i < primary_steps - 1:
                        self._move_relative(primary_axis, direction * dimensions['resolution'])
                        time.sleep(0.1)
                    
                    # Update progress bar
                    pbar.update(1)
                    pbar.refresh()  # Force refresh to keep display clean
                
                # Move along secondary axis if not at end of scan
                if j < secondary_steps - 1:
                    self._move_relative(secondary_axis, dimensions['resolution'])
                    time.sleep(0.1)
                    
        finally:
            pbar.close()