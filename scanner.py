"""
Core scanning logic
Handles scan patterns, data acquisition (scope scaling)
"""

import time
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging


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
            if distance != 0:
                self._move_relative(axis, distance)
                time.sleep(0.1)  # Small delay between movements
    
    def _collect_datapoint(self) -> Tuple[float, float]:
        """
        Collect a single datapoint with automatic vertical scaling
        Simplified version matching MATLAB implementation
        Returns: (peak_positive, peak_negative)
        """
        pos_peak, neg_peak = self.hardware.get_measurement()
        
        # Get current vertical scale
        current_scale = float(self.hardware.scope.query("CH1:Scale?"))
        
        # Check if scaling needed
        max_signal = max(abs(pos_peak), abs(neg_peak))
        
        if max_signal > self.upper_limit:
            # Signal too large - increase scale
            new_scale = current_scale * max_signal / self.upper_limit
            if new_scale >= self.rounding_bin:
                self.hardware.scope.write(f"CH1:Scale {new_scale}")
                pos_peak, neg_peak = self.hardware.get_measurement()
            
        elif max_signal < self.lower_limit and current_scale > self.rounding_bin:
            # Signal too small - decrease scale
            new_scale = current_scale * max_signal / self.lower_limit
            new_scale = max(new_scale, self.rounding_bin)  # Don't go below minimum scale
            self.hardware.scope.write(f"CH1:Scale {new_scale}")
            pos_peak, neg_peak = self.hardware.get_measurement()
            
        return pos_peak, neg_peak

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
            logging.error(f"Scan error: {e}")
            raise
            
        finally:
            self._return_to_start()
            
        return self.data

    def _run_1d_scan(self, axis: str, dimensions: Dict) -> None:
        """
        Execute 1D scan along specified axis
        
        Args:
            axis: 'x', 'y', or 'z'
            dimensions: dict with 'range' and 'resolution'
        """
        distance = dimensions['range']
        step_size = dimensions['resolution']
        steps = int(distance / step_size)
        
        # Move to start position (negative half of range)
        start_offset = -distance / 2
        self._move_relative(axis, start_offset)
        time.sleep(0.2)
        
        # Execute scan
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

    def _run_2d_scan(self, axes: str, dimensions: Dict) -> None:
        """
        Execute 2D scan in specified plane
        
        Args:
            axes: 'xy', 'xz', or 'yz'
            dimensions: dict with ranges and resolution
        """
        # Parse axes
        primary_axis = axes[0]
        secondary_axis = axes[1]
        
        # Calculate steps for each axis
        # primary_steps = int(dimensions[f'{primary_axis}_range'] / dimensions['resolution'])
        # secondary_steps = int(dimensions[f'{secondary_axis}_range'] / dimensions['resolution'])
        
        # Move to start position (negative half of both ranges)
        # self._move_relative(primary_axis, -dimensions[f'{primary_axis}_range'] / 2)
        # self._move_relative(secondary_axis, -dimensions[f'{secondary_axis}_range'] / 2)


        primary_steps = int(dimensions[primary_axis] / dimensions['resolution'])
        secondary_steps = int(dimensions[secondary_axis] / dimensions['resolution'])
        self._move_relative(primary_axis, -dimensions[primary_axis] / 2)
        self._move_relative(secondary_axis, -dimensions[secondary_axis] / 2)
        time.sleep(0.2)
        
        # Execute serpentine scan pattern
        for j in range(secondary_steps):
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
                
                # Move along primary axis if not at end of line
                if i < primary_steps - 1:
                    self._move_relative(primary_axis, direction * dimensions['resolution'])
                    time.sleep(0.1)
            
            # Move along secondary axis if not at end of scan
            if j < secondary_steps - 1:
                self._move_relative(secondary_axis, dimensions['resolution'])
                time.sleep(0.1)

