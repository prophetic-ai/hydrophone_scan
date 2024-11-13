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
        Collect a single datapoint
        Returns: (peak_positive, peak_negative)
        """
        return self.hardware.get_measurement()

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
        
        Args:
            axis: 'x', 'y', or 'z'
            dimensions: dict with ranges and resolution
        """
        distance = dimensions[axis]
        step_size = dimensions['resolution']
        steps = int(distance / step_size)
        
        # Move to start position
        print(f"\nMoving to scan start position...")
        start_offset = -distance / 2
        self._move_relative(axis, start_offset)
        time.sleep(0.2)
        
        # Execute scan with progress bar
        print(f"\nStarting {axis}-axis scan ({steps} points)...")
        with tqdm(total=steps, desc=f"Scanning {axis}-axis", 
                 bar_format='{desc}: {percentage:3.1f}%|{bar:50}| {n_fmt}/{total_fmt} pts [{elapsed}<{remaining}]',
                 ascii=False, ncols=120, leave=True) as pbar:
            
            for i in range(steps):
                # Collect data
                pos_peak, neg_peak = self._collect_datapoint()
                position = self.current_position.copy()
                self.data.append({
                    'position': position,
                    'peaks': (pos_peak, neg_peak)
                })
                
                # Move to next position if not at end
                if i < steps - 1:
                    self._move_relative(axis, step_size)
                    time.sleep(0.1)
                
                pbar.update(1)

    def _run_2d_scan(self, axes: str, dimensions: Dict) -> None:
        """
        Execute 2D scan in specified plane
        
        Args:
            axes: 'xy', 'xz', or 'yz'
            dimensions: dict with ranges and resolution
        """
        primary_axis = axes[0]
        secondary_axis = axes[1]
        
        # Calculate steps
        primary_steps = int(dimensions[primary_axis] / dimensions['resolution'])
        secondary_steps = int(dimensions[secondary_axis] / dimensions['resolution'])
        total_points = primary_steps * secondary_steps
        
        # Move to start position
        print(f"\nMoving to scan start position...")
        self._move_relative(primary_axis, -dimensions[primary_axis] / 2)
        self._move_relative(secondary_axis, -dimensions[secondary_axis] / 2)
        time.sleep(0.2)
        
        # Execute serpentine scan pattern with progress bar
        print(f"\nStarting {axes}-plane scan ({total_points} points, {secondary_steps} rows)...")
        
        with tqdm(total=total_points, 
                 desc=f"Scanning {axes}-plane",
                 ncols=100) as pbar:
            
            for j in range(secondary_steps):
                # Update description with current row
                pbar.set_description(f"Scanning {axes}-plane [Row {j+1}/{secondary_steps}]")
                
                # Determine primary axis direction for this row
                direction = 1 if j % 2 == 0 else -1
                
                # Scan along primary axis
                for i in range(primary_steps):
                    # Collect data
                    pos_peak, neg_peak = self._collect_datapoint()
                    position = self.current_position.copy()
                    self.data.append({
                        'position': position,
                        'peaks': (pos_peak, neg_peak)
                    })
                    
                    # Move to next position if not at end of line
                    if i < primary_steps - 1:
                        self._move_relative(primary_axis, direction * dimensions['resolution'])
                        time.sleep(0.1)

                    pbar.update(1)
                
                # Move along secondary axis if not at end of scan
                if j < secondary_steps - 1:
                    self._move_relative(secondary_axis, dimensions['resolution'])
                    time.sleep(0.1)