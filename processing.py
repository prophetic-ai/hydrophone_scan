"""
Data processing and visualization for Hydrophone Scanner
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple
import os
import json
import logging
from datetime import datetime

class DataProcessor:
    def __init__(self, config: Dict):
        self.config = config
        self.calibration_value = config['scan']['calibration_value']
        self.scan_type = config['scan']['type']
        self.dimensions = config['scan']['dimensions']
        self.base_path = config['scan']['base_path']
        
    def _convert_to_pressure(self, voltage: float) -> float:
        """Convert voltage to pressure (MPa)"""
        return voltage / self.calibration_value
    
    def _format_coordinate(self, value: float) -> str:

        """Convert coordinate value to string format like '0p50' or '-1p25'"""
        # Replace decimal point with 'p' and ensure two decimal places
        return f"{value:.2f}".replace('.', 'p').replace('-', 'n')

    def _create_pressure_map(self, data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Create pressure maps from scan data"""
        if self.scan_type.startswith('1d'):
            axis = self.scan_type[-1]
            size = int(self.dimensions[axis] / self.dimensions['resolution'])
            pos_map = np.zeros(size)
            neg_map = np.zeros(size)
            
            for i, point in enumerate(data):
                pos_map[i] = self._convert_to_pressure(point['peaks'][0])
                neg_map[i] = self._convert_to_pressure(point['peaks'][1])
                
        else:  # 2D scan
            axes = self.scan_type[-2:]
            size_x = int(self.dimensions[axes[0]] / self.dimensions['resolution'])
            size_y = int(self.dimensions[axes[1]] / self.dimensions['resolution'])
            pos_map = np.zeros((size_y, size_x))
            neg_map = np.zeros((size_y, size_x))
            
            for i, point in enumerate(data):
                y_idx = i // size_x
                x_idx = i % size_x
                if y_idx % 2 == 1:  # Serpentine pattern correction
                    x_idx = size_x - 1 - x_idx
                pos_map[y_idx, x_idx] = self._convert_to_pressure(point['peaks'][0])
                neg_map[y_idx, x_idx] = self._convert_to_pressure(point['peaks'][1])
                
        return pos_map, neg_map

    def _calculate_fwhm(self, pressure_map: np.ndarray) -> float:
        """Calculate Full Width at Half Maximum"""
        if pressure_map.ndim == 1:
            profile = pressure_map
        else:
            max_idx = np.unravel_index(np.argmax(pressure_map), pressure_map.shape)
            if pressure_map.shape[0] >= pressure_map.shape[1]:
                profile = pressure_map[:, max_idx[1]]
            else:
                profile = pressure_map[max_idx[0], :]
                
        half_max = np.max(profile) / 2
        above_half = profile >= half_max
        edges = np.where(np.diff(above_half))[0]
        
        if len(edges) >= 2:
            fwhm = (edges[1] - edges[0]) * self.dimensions['resolution']
            return fwhm
        return None

    def _save_plots(self, pos_map: np.ndarray, neg_map: np.ndarray, save_path: str) -> None:
        matplotlib.use('Agg')  # Use Agg backend to avoid display issues
        """Generate and save pressure map plots"""
        if pos_map.ndim == 1:  # 1D plot
            # Create figure for 1D plots
            plt.figure(figsize=(10, 8))
            
            # Calculate x-axis values centered at 0
            num_points = len(pos_map)
            step_size = self.dimensions['resolution']
            x = np.linspace(-step_size * (num_points-1)/2, 
                        step_size * (num_points-1)/2, 
                        num_points)
            
            # Positive pressure subplot
            plt.subplot(2, 1, 1)
            plt.plot(x, pos_map, 'b-')
            plt.title('Peak Positive Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Pressure (MPa)')
            plt.grid(True)
            plt.axvline(x=0, color='k', linestyle='--', alpha=0.3)
            
            # Add FWHM if calculable
            fwhm = self._calculate_fwhm(pos_map)
            if fwhm:
                plt.text(0.02, 0.95, f'FWHM: {fwhm:.2f} mm', 
                        transform=plt.gca().transAxes)
            
            # Negative pressure subplot
            plt.subplot(2, 1, 2)
            plt.plot(x, np.abs(neg_map), 'r-')
            plt.title('Peak Negative Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Pressure (MPa)')
            plt.grid(True)
            plt.axvline(x=0, color='k', linestyle='--', alpha=0.3)
            
        else:  # 2D plot
            # Create figure for 2D plots
            fig = plt.figure(figsize=(15, 6))
            
            # Calculate extent for proper scaling
            extent = [0, pos_map.shape[1] * self.dimensions['resolution'],
                     0, pos_map.shape[0] * self.dimensions['resolution']]
            
            # Positive pressure plot
            plt.subplot(1, 2, 1)
            plt.imshow(pos_map, extent=extent, origin='lower', cmap='jet')
            plt.colorbar(label='Pressure (MPa)')
            plt.title('Peak Positive Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Position (mm)')
            
            # Add FWHM if calculable
            fwhm = self._calculate_fwhm(pos_map)
            if fwhm:
                plt.text(0.02, 0.95, f'FWHM: {fwhm:.2f} mm', 
                        transform=plt.gca().transAxes, color='white')
            
            # Negative pressure plot
            plt.subplot(1, 2, 2)
            plt.imshow(np.abs(neg_map), extent=extent, origin='lower', cmap='jet')
            plt.colorbar(label='Pressure (MPa)')
            plt.title('Peak Negative Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Position (mm)')
        
        plt.tight_layout()
        plt.savefig(os.path.join(save_path, 'pressure_maps.png'), dpi=300, bbox_inches='tight')

        matplotlib.use('TkAgg')  # Use TkAgg backend for interactive plots
        plt.show(block=False)
        matplotlib.use('Agg')  # Revert to Agg backend after showing
        # plt.close()


    def _save_plots(self, pos_map: np.ndarray, neg_map: np.ndarray, save_path: str) -> None:
        """Generate, save, and display pressure map plots"""
        # Import and configure matplotlib if not already done
        import matplotlib
        matplotlib.use('TkAgg')  # Use TkAgg backend for interactive plots
        import matplotlib.pyplot as plt
        
        if pos_map.ndim == 1:  # 1D plot
            # Create figure for 1D plots
            plt.figure(figsize=(10, 8))
            
            # Calculate total scan distance and center it around 0
            total_distance = len(pos_map) * self.dimensions['resolution']
            x = np.linspace(-total_distance/2, total_distance/2, len(pos_map))
            
            # Positive pressure subplot
            plt.subplot(2, 1, 1)
            plt.plot(x, pos_map, 'b-', linewidth=2)
            plt.title('Peak Positive Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Pressure (MPa)')
            plt.grid(True)
            plt.axvline(x=0, color='k', linestyle='--', alpha=0.3)
            
            # Ensure x-axis is centered
            plt.xlim(-total_distance/2, total_distance/2)
            
            # Add FWHM if calculable
            fwhm = self._calculate_fwhm(pos_map)
            if fwhm:
                plt.text(0.02, 0.95, f'FWHM: {fwhm:.2f} mm', 
                        transform=plt.gca().transAxes)
            
            # Negative pressure subplot
            plt.subplot(2, 1, 2)
            plt.plot(x, np.abs(neg_map), 'r-', linewidth=2)
            plt.title('Peak Negative Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Pressure (MPa)')
            plt.grid(True)
            plt.axvline(x=0, color='k', linestyle='--', alpha=0.3)
            
            # Ensure x-axis is centered
            plt.xlim(-total_distance/2, total_distance/2)
        
        else:  # 2D plot
            # Create figure for 2D plots
            fig = plt.figure(figsize=(15, 6))
            
            # Calculate extent for proper scaling
            extent = [0, pos_map.shape[1] * self.dimensions['resolution'],
                    0, pos_map.shape[0] * self.dimensions['resolution']]
            
            # Positive pressure plot
            plt.subplot(1, 2, 1)
            pos_im = plt.imshow(pos_map, extent=extent, origin='lower', cmap='jet')
            plt.colorbar(pos_im, label='Pressure (MPa)')
            plt.title('Peak Positive Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Position (mm)')
            
            # Add FWHM if calculable
            fwhm = self._calculate_fwhm(pos_map)
            if fwhm:
                plt.text(0.02, 0.95, f'FWHM: {fwhm:.2f} mm', 
                        transform=plt.gca().transAxes, color='white')
            
            # Negative pressure plot
            plt.subplot(1, 2, 2)
            neg_im = plt.imshow(np.abs(neg_map), extent=extent, origin='lower', cmap='jet')
            plt.colorbar(neg_im, label='Pressure (MPa)')
            plt.title('Peak Negative Pressure')
            plt.xlabel('Position (mm)')
            plt.ylabel('Position (mm)')
    
        plt.tight_layout()
    
        # Save the plot
        plt.savefig(os.path.join(save_path, 'pressure_maps.png'), dpi=300, bbox_inches='tight')
        
        # Show plot - it will be interactive and non-blocking
        plt.show(block=False)

    def process_and_save(self, data: List[Dict], scan_id: str) -> None:
        """Process and save scan data with visualizations"""
        # Create scan directory
        scan_path = os.path.join(self.base_path, scan_id)
        os.makedirs(scan_path, exist_ok=True)

        # Get save options from config
        save_options = self.config['scan'].get('save_options', {})
        save_waveforms = save_options.get('save_waveforms', True)
        waveform_decimation = save_options.get('waveform_decimation', 1)

        if save_waveforms:
            waveforms_path = os.path.join(scan_path, 'waveforms')
            os.makedirs(waveforms_path, exist_ok=True)
        
        # Process data
        pos_map, neg_map = self._create_pressure_map(data)
        
        # Find peak pressures
        peak_pos = np.max(pos_map)
        peak_neg = np.min(neg_map)
        
        # Calculate scan center based on dimensions
        center = {
            'x': self.dimensions.get('x', 0) / 2,
            'y': self.dimensions.get('y', 0) / 2,
            'z': self.dimensions.get('z', 0) / 2
        }
        
        # Save processed data
        processed_data = []
        for i, point in enumerate(data):
            point_data = {
                'position': point['position'],
                'peaks': point['peaks']
            }
            processed_data.append(point_data)
            
            # Save waveform if enabled and meets decimation criteria
            if save_waveforms and i % waveform_decimation == 0:
                if point.get('waveform') and point['waveform']['time'] is not None:
                    # Calculate relative position from center
                    rel_pos = {
                        'x': point['position']['x'] - center['x'],
                        'y': point['position']['y'] - center['y'],
                        'z': point['position']['z'] - center['z']
                    }
                    
                    # Create filename with relative coordinates
                    filename = f"X{self._format_coordinate(rel_pos['x'])}_" \
                            f"Y{self._format_coordinate(rel_pos['y'])}_" \
                            f"Z{self._format_coordinate(rel_pos['z'])}.json"
                    
                    waveform_data = {
                        'waveform': point['waveform'],
                        'position': {
                            'absolute': point['position'],
                            'relative': rel_pos
                        },
                        'peaks': point['peaks'],
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    waveform_file = os.path.join(waveforms_path, filename)
                    with open(waveform_file, 'w') as f:
                        json.dump(waveform_data, f, indent=2)
        
        # Save scan metadata
        metadata = {
            'config': self.config,
            'scan_data': processed_data,
            'timestamp': datetime.now().isoformat(),
            'peak_positive': float(peak_pos),
            'peak_negative': float(peak_neg),
            'center_position': center,
            'waveform_config': {
                'saved': save_waveforms,
                'decimation': waveform_decimation,
            }
        }
        
        with open(os.path.join(scan_path, 'scan_metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Generate and save plots
        self._save_plots(pos_map, neg_map, scan_path)
        
        # Save numpy arrays
        np.save(os.path.join(scan_path, 'pos_pressure.npy'), pos_map)
        np.save(os.path.join(scan_path, 'neg_pressure.npy'), neg_map)
        
        # Print summary
        print(f"\nScan processed and saved to: {scan_path}")
        print(f"Peak Positive Pressure: {peak_pos:.2f} MPa")
        print(f"Peak Negative Pressure: {peak_neg:.2f} MPa")
        if save_waveforms:
            print(f"Waveforms saved in: {waveforms_path}")
            if waveform_decimation > 1:
                print(f"Saving every {waveform_decimation}th waveform")
        
        if self.scan_type.startswith('2d'):
            fwhm = self._calculate_fwhm(pos_map)
            if fwhm:
                print(f"FWHM: {fwhm:.2f} mm")
