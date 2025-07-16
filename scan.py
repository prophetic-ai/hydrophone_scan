#!/usr/bin/env python3
"""
Arduino Movement Control CLI with Oscilloscope Sampling and Automated Scanning
Provides command-line interface for controlling the hydrophone scanner movements,
sampling voltage data from the oscilloscope, and performing automated area scans
"""

import sys
import os
import time
import pyvisa
import numpy as np
import warnings
import json
import csv
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Add the current directory to Python path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hardware import HardwareController
from config import load_config

class ArduinoController:
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize Arduino controller with configuration"""
        try:
            self.config = load_config(config_path)
            print(f"✅ Loaded configuration from {config_path}")
            
            # Initialize hardware controller (Arduino only, no oscilloscope)
            self.hardware = HardwareController(
                arduino_port=self.config['hardware']['arduino_port'],
                scope_address=None,  # We'll handle oscilloscope separately
                config=self.config
            )
            
            # Initialize oscilloscope connection
            self.scope = None
            self.scope_settings = {}
            self.consecutive_errors = 0
            self._connect_oscilloscope()
            
            print("✅ Arduino controller initialized successfully")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            sys.exit(1)

    def _connect_oscilloscope(self):
        """Connect to oscilloscope using robust methods from oscilloscope_test.py"""
        scope_address = self.config['hardware']['scope_address']
        
        if not scope_address:
            print("⚠️  No oscilloscope address in config - voltage sampling disabled")
            return
        
        try:
            print("\n🔗 Connecting to Siglent oscilloscope...")
            
            # Suppress USB firmware warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="pyvisa_py")
            
            rm = pyvisa.ResourceManager()
            self.scope = rm.open_resource(scope_address)
            self.scope.timeout = 15000  # Longer timeout for USB issues
            
            # More robust connection with retries
            connected = False
            for attempt in range(3):
                try:
                    self.scope.write('CHDR OFF')
                    time.sleep(0.5)
                    
                    # Test basic communication
                    idn = self.scope.query('*IDN?')
                    print(f"✅ Oscilloscope connected: {idn.strip()}")
                    connected = True
                    break
                    
                except Exception as e:
                    print(f"Connection attempt {attempt + 1} failed: {e}")
                    time.sleep(1)
            
            if not connected:
                print("❌ Could not establish stable oscilloscope connection")
                self.scope = None
                return
            
            # Read current settings
            self._read_scope_settings()
            
        except Exception as e:
            print(f"❌ Oscilloscope connection error: {e}")
            self.scope = None

    def _read_scope_settings(self):
        """Read and store current oscilloscope settings"""
        if not self.scope:
            return
            
        print("📋 Reading oscilloscope settings...")
        
        setting_queries = {
            'vdiv': 'C1:VDIV?',
            'tdiv': 'TDIV?',
            'coupling': 'C1:CPL?',
            'trigger_mode': 'TRMD?',
            'offset': 'C1:OFST?'
        }
        
        for setting, query in setting_queries.items():
            try:
                response = self.scope.query(query)
                self.scope_settings[setting] = response.strip()
                print(f"  {setting}: {response.strip()}")
            except Exception as e:
                print(f"  ⚠️  Could not read {setting}: {e}")
                self.scope_settings[setting] = None

    def sample_voltage_detailed(self) -> dict:
        """Sample voltage with detailed breakdown: positive peak, negative peak, and peak-to-peak"""
        if not self.scope:
            print("❌ Oscilloscope not connected")
            return None
        
        try:
            # Method 1: Try to get individual peak measurements
            pos_peak = None
            neg_peak = None
            vpp = None
            method_used = None
            
            # Try to get positive peak
            pos_peak_methods = [
                ('PAVA_MAX', 'C1:PAVA? MAX'),
                ('MEAS_VMAX', 'MEAS:VMAX? C1'),
                ('PARA_MAX', 'PARA? C1,MAX')
            ]
            
            for method_name, command in pos_peak_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        pos_peak = float(value_str.rstrip('V'))
                        method_used = method_name
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        pos_peak = float(response.strip())
                        method_used = method_name
                        break
                except Exception:
                    continue
            
            # Try to get negative peak
            neg_peak_methods = [
                ('PAVA_MIN', 'C1:PAVA? MIN'),
                ('MEAS_VMIN', 'MEAS:VMIN? C1'),
                ('PARA_MIN', 'PARA? C1,MIN')
            ]
            
            for method_name, command in neg_peak_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        neg_peak = float(value_str.rstrip('V'))
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        neg_peak = float(response.strip())
                        break
                except Exception:
                    continue
            
            # Try to get peak-to-peak
            vpp_methods = [
                ('PAVA_PKPK', 'C1:PAVA? PKPK'),
                ('MEAS_VAMP', 'MEAS:VAMP? C1'),
                ('PARA_PKPK', 'PARA? C1,PKPK')
            ]
            
            for method_name, command in vpp_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        vpp = float(value_str.rstrip('V'))
                        if not method_used:
                            method_used = method_name
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        vpp = float(response.strip())
                        if not method_used:
                            method_used = method_name
                        break
                except Exception:
                    continue
            
            # If individual peaks failed, try waveform method
            if pos_peak is None or neg_peak is None:
                try:
                    self.scope.write('C1:WF? DAT1')
                    time.sleep(0.5)
                    
                    raw_data = self.scope.read_raw()
                    
                    if len(raw_data) > 10:
                        # Try to parse waveform data
                        data = None
                        try:
                            if b'#9' in raw_data:
                                header_end = raw_data.find(b'#9') + 11
                                data_bytes = raw_data[header_end:-1]
                                data = np.frombuffer(data_bytes, dtype=np.int8)
                            elif len(raw_data) > 16:
                                data_bytes = raw_data[16:-1]
                                data = np.frombuffer(data_bytes, dtype=np.int8)
                        except:
                            pass
                        
                        if data is not None and len(data) > 0:
                            # Get current scaling
                            vdiv_val = 1.0
                            offset_val = 0.0
                            
                            if self.scope_settings.get('vdiv'):
                                try:
                                    vdiv_val = float(self.scope_settings['vdiv'].split()[-1].strip('V'))
                                except:
                                    pass
                            
                            if self.scope_settings.get('offset'):
                                try:
                                    offset_val = float(self.scope_settings['offset'].split()[-1].strip('V'))
                                except:
                                    pass
                            
                            # Convert to voltage
                            voltage_array = (data / 25.0) * vdiv_val + offset_val
                            
                            pos_peak = np.max(voltage_array)
                            neg_peak = np.min(voltage_array)
                            vpp = pos_peak - neg_peak
                            method_used = 'WAVEFORM'
                
                except Exception as e:
                    pass
            
            # Calculate missing values if we have some data
            if pos_peak is not None and neg_peak is not None and vpp is None:
                vpp = pos_peak - neg_peak
            elif vpp is not None and pos_peak is not None and neg_peak is None:
                neg_peak = pos_peak - vpp
            elif vpp is not None and neg_peak is not None and pos_peak is None:
                pos_peak = neg_peak + vpp
            
            if pos_peak is not None or neg_peak is not None or vpp is not None:
                self.consecutive_errors = 0
                return {
                    'positive_peak': pos_peak,
                    'negative_peak': neg_peak,
                    'peak_to_peak': vpp,
                    'method': method_used
                }
            
            # If all methods fail
            self.consecutive_errors += 1
            return None
            
        except Exception as e:
            self.consecutive_errors += 1
            print(f"❌ Voltage sampling error: {e}")
            return None

    def continuous_sampling(self):
        """Continuous voltage sampling mode with detailed breakdown"""
        if not self.scope:
            print("❌ Oscilloscope not connected - cannot sample voltage")
            return
        
        print("\n📊 Continuous Voltage Sampling")
        print("=" * 70)
        print("Press Ctrl+C to stop sampling")
        print("=" * 70)
        print(f"{'Sample':>6} {'Pos Peak':>10} {'Neg Peak':>10} {'Peak-Peak':>10} {'Method':>12}")
        print("-" * 70)
        
        sample_count = 0
        
        try:
            while True:
                voltage_data = self.sample_voltage_detailed()
                
                if voltage_data:
                    sample_count += 1
                    pos_peak = voltage_data['positive_peak']
                    neg_peak = voltage_data['negative_peak']
                    vpp = voltage_data['peak_to_peak']
                    method = voltage_data['method']
                    
                    # Format the output
                    pos_str = f"{pos_peak:+7.3f}V" if pos_peak is not None else "   N/A  "
                    neg_str = f"{neg_peak:+7.3f}V" if neg_peak is not None else "   N/A  "
                    vpp_str = f"{vpp:7.3f}V" if vpp is not None else "   N/A "
                    
                    print(f"{sample_count:6d} {pos_str:>10} {neg_str:>10} {vpp_str:>10} {method:>12}")
                    
                    self.consecutive_errors = 0
                else:
                    print(f"⚠️  No measurement available (error count: {self.consecutive_errors})")
                    
                    if self.consecutive_errors > 5:
                        print("Too many consecutive errors - trying to reconnect...")
                        self._connect_oscilloscope()
                
                time.sleep(1)  # Slower sampling to reduce USB stress
                
        except KeyboardInterrupt:
            print("\n\n🛑 Sampling stopped by user")

    def generate_scan_points(self, axes: str, distances: Dict[str, float], increment: float, start_pos: Dict[str, float]) -> List[Dict[str, float]]:
        """Generate scan points using snake/raster pattern for efficient scanning"""
        points = []
        
        if axes == 'x':
            distance = distances['x']
            if distance == 0:
                points.append({'x': start_pos['x'], 'y': start_pos['y'], 'z': start_pos['z']})
            else:
                # Generate points from 0 to distance with proper step direction
                if distance > 0:
                    x_vals = np.arange(0, distance + increment/2, increment)
                else:
                    x_vals = np.arange(0, distance - increment/2, -increment)
                
                for x_offset in x_vals:
                    points.append({'x': start_pos['x'] + x_offset, 'y': start_pos['y'], 'z': start_pos['z']})
                
        elif axes == 'y':
            distance = distances['y']
            if distance == 0:
                points.append({'x': start_pos['x'], 'y': start_pos['y'], 'z': start_pos['z']})
            else:
                if distance > 0:
                    y_vals = np.arange(0, distance + increment/2, increment)
                else:
                    y_vals = np.arange(0, distance - increment/2, -increment)
                
                for y_offset in y_vals:
                    points.append({'x': start_pos['x'], 'y': start_pos['y'] + y_offset, 'z': start_pos['z']})
                
        elif axes == 'z':
            distance = distances['z']
            if distance == 0:
                points.append({'x': start_pos['x'], 'y': start_pos['y'], 'z': start_pos['z']})
            else:
                if distance > 0:
                    z_vals = np.arange(0, distance + increment/2, increment)
                else:
                    z_vals = np.arange(0, distance - increment/2, -increment)
                
                for z_offset in z_vals:
                    points.append({'x': start_pos['x'], 'y': start_pos['y'], 'z': start_pos['z'] + z_offset})
                
        elif axes == 'xy':
            # Snake pattern for XY scan
            x_distance = distances['x']
            y_distance = distances['y']
            
            # Generate X values
            if x_distance == 0:
                x_vals = [0]
            elif x_distance > 0:
                x_vals = np.arange(0, x_distance + increment/2, increment)
            else:
                x_vals = np.arange(0, x_distance - increment/2, -increment)
            
            # Generate Y values
            if y_distance == 0:
                y_vals = [0]
            elif y_distance > 0:
                y_vals = np.arange(0, y_distance + increment/2, increment)
            else:
                y_vals = np.arange(0, y_distance - increment/2, -increment)
            
            # Create snake pattern: alternate X direction for each Y row
            for i, y_offset in enumerate(y_vals):
                if i % 2 == 0:
                    # Even rows: scan X in normal direction
                    current_x_vals = x_vals
                else:
                    # Odd rows: scan X in reverse direction
                    current_x_vals = x_vals[::-1]
                
                for x_offset in current_x_vals:
                    points.append({'x': start_pos['x'] + x_offset, 'y': start_pos['y'] + y_offset, 'z': start_pos['z']})
                    
        elif axes == 'xz':
            # Snake pattern for XZ scan
            x_distance = distances['x']
            z_distance = distances['z']
            
            # Generate X values
            if x_distance == 0:
                x_vals = [0]
            elif x_distance > 0:
                x_vals = np.arange(0, x_distance + increment/2, increment)
            else:
                x_vals = np.arange(0, x_distance - increment/2, -increment)
            
            # Generate Z values
            if z_distance == 0:
                z_vals = [0]
            elif z_distance > 0:
                z_vals = np.arange(0, z_distance + increment/2, increment)
            else:
                z_vals = np.arange(0, z_distance - increment/2, -increment)
            
            # Create snake pattern: alternate X direction for each Z row
            for i, z_offset in enumerate(z_vals):
                if i % 2 == 0:
                    # Even rows: scan X in normal direction
                    current_x_vals = x_vals
                else:
                    # Odd rows: scan X in reverse direction
                    current_x_vals = x_vals[::-1]
                
                for x_offset in current_x_vals:
                    points.append({'x': start_pos['x'] + x_offset, 'y': start_pos['y'], 'z': start_pos['z'] + z_offset})
                    
        elif axes == 'yz':
            # Snake pattern for YZ scan
            y_distance = distances['y']
            z_distance = distances['z']
            
            # Generate Y values
            if y_distance == 0:
                y_vals = [0]
            elif y_distance > 0:
                y_vals = np.arange(0, y_distance + increment/2, increment)
            else:
                y_vals = np.arange(0, y_distance - increment/2, -increment)
            
            # Generate Z values
            if z_distance == 0:
                z_vals = [0]
            elif z_distance > 0:
                z_vals = np.arange(0, z_distance + increment/2, increment)
            else:
                z_vals = np.arange(0, z_distance - increment/2, -increment)
            
            # Create snake pattern: alternate Y direction for each Z row
            for i, z_offset in enumerate(z_vals):
                if i % 2 == 0:
                    # Even rows: scan Y in normal direction
                    current_y_vals = y_vals
                else:
                    # Odd rows: scan Y in reverse direction
                    current_y_vals = y_vals[::-1]
                
                for y_offset in current_y_vals:
                    points.append({'x': start_pos['x'], 'y': start_pos['y'] + y_offset, 'z': start_pos['z'] + z_offset})
                    
        elif axes == 'xyz':
            # Snake pattern for XYZ scan
            x_distance = distances['x']
            y_distance = distances['y']
            z_distance = distances['z']
            
            # Generate X values
            if x_distance == 0:
                x_vals = [0]
            elif x_distance > 0:
                x_vals = np.arange(0, x_distance + increment/2, increment)
            else:
                x_vals = np.arange(0, x_distance - increment/2, -increment)
            
            # Generate Y values
            if y_distance == 0:
                y_vals = [0]
            elif y_distance > 0:
                y_vals = np.arange(0, y_distance + increment/2, increment)
            else:
                y_vals = np.arange(0, y_distance - increment/2, -increment)
            
            # Generate Z values
            if z_distance == 0:
                z_vals = [0]
            elif z_distance > 0:
                z_vals = np.arange(0, z_distance + increment/2, increment)
            else:
                z_vals = np.arange(0, z_distance - increment/2, -increment)
            
            # Create 3D snake pattern: alternate XY plane direction for each Z layer
            for k, z_offset in enumerate(z_vals):
                for i, y_offset in enumerate(y_vals):
                    # Alternate X direction for each Y row
                    if i % 2 == 0:
                        current_x_vals = x_vals
                    else:
                        current_x_vals = x_vals[::-1]
                    
                    # For odd Z layers, reverse the entire Y traversal
                    if k % 2 == 1:
                        current_x_vals = current_x_vals[::-1]
                    
                    for x_offset in current_x_vals:
                        points.append({'x': start_pos['x'] + x_offset, 'y': start_pos['y'] + y_offset, 'z': start_pos['z'] + z_offset})
        
        return points

    def move_to_position(self, target_position: Dict[str, float]) -> bool:
        """Move to absolute position"""
        current_pos = self.hardware.get_current_position()
        
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

    def generate_heatmaps(self, csv_file: Path, scan_dir: Path, axes: str):
        """Generate heatmap visualizations from scan data"""
        try:
            print(f"\n📊 Generating heatmaps...")
            
            # Read CSV data
            data = []
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Skip failed measurements
                    if row['method'] == 'FAILED':
                        continue
                    
                    # Convert to float, handle None values
                    try:
                        x = float(row['x_mm'])
                        y = float(row['y_mm'])
                        z = float(row['z_mm'])
                        pos_peak = float(row['positive_peak_v']) if row['positive_peak_v'] and row['positive_peak_v'] != 'None' else None
                        neg_peak = float(row['negative_peak_v']) if row['negative_peak_v'] and row['negative_peak_v'] != 'None' else None
                        
                        data.append({
                            'x': x, 'y': y, 'z': z,
                            'pos_peak': pos_peak,
                            'neg_peak': neg_peak
                        })
                    except (ValueError, TypeError):
                        continue
            
            if not data:
                print("⚠️  No valid data points for heatmap generation")
                return
            
            # Determine which axes to plot based on scan type
            if axes in ['x', 'y', 'z']:
                print(f"⚠️  1D scan detected - heatmaps require 2D data")
                return
            elif axes == 'xy':
                self._create_2d_heatmap(data, 'x', 'y', scan_dir)
            elif axes == 'xz':
                self._create_2d_heatmap(data, 'x', 'z', scan_dir)
            elif axes == 'yz':
                self._create_2d_heatmap(data, 'y', 'z', scan_dir)
            elif axes == 'xyz':
                # For 3D scans, create multiple 2D slices or use first two axes
                print(f"📊 3D scan detected - creating X-Y heatmaps")
                self._create_2d_heatmap(data, 'x', 'y', scan_dir)
            
            print(f"✅ Heatmaps saved to {scan_dir}")
            
        except Exception as e:
            print(f"❌ Error generating heatmaps: {e}")

    def _create_2d_heatmap(self, data: List[Dict], x_axis: str, y_axis: str, scan_dir: Path):
        """Create 2D heatmaps for positive and negative voltage peaks"""
        
        # Extract coordinates and voltage data
        x_coords = [d[x_axis] for d in data]
        y_coords = [d[y_axis] for d in data]
        pos_peaks = [d['pos_peak'] for d in data if d['pos_peak'] is not None]
        neg_peaks = [d['neg_peak'] for d in data if d['neg_peak'] is not None]
        
        if not pos_peaks and not neg_peaks:
            print("⚠️  No valid voltage data for heatmap generation")
            return
        
        # Get unique coordinates for grid
        unique_x = sorted(set(x_coords))
        unique_y = sorted(set(y_coords))
        
        # Create coordinate to index mapping
        x_to_idx = {x: i for i, x in enumerate(unique_x)}
        y_to_idx = {y: i for i, y in enumerate(unique_y)}
        
        # Create grids
        pos_grid = np.full((len(unique_y), len(unique_x)), np.nan)
        neg_grid = np.full((len(unique_y), len(unique_x)), np.nan)
        
        # Fill grids with data
        for d in data:
            x_idx = x_to_idx[d[x_axis]]
            y_idx = y_to_idx[d[y_axis]]
            
            if d['pos_peak'] is not None:
                pos_grid[y_idx, x_idx] = d['pos_peak']
            if d['neg_peak'] is not None:
                neg_grid[y_idx, x_idx] = d['neg_peak']
        
        # Calculate global min/max for consistent color scaling
        all_pos_values = [v for v in pos_peaks if not np.isnan(v)]
        all_neg_values = [v for v in neg_peaks if not np.isnan(v)]
        
        # Create positive voltage heatmap
        if all_pos_values:
            plt.figure(figsize=(10, 8))
            
            vmin_pos = min(all_pos_values)
            vmax_pos = max(all_pos_values)
            
            im = plt.imshow(pos_grid, 
                          extent=[min(unique_x), max(unique_x), min(unique_y), max(unique_y)],
                          origin='lower', 
                          cmap='coolwarm',
                          vmin=vmin_pos, 
                          vmax=vmax_pos,
                          interpolation='nearest')
            
            plt.colorbar(im, label='Voltage (V)')
            plt.xlabel(f'{x_axis.upper()}-axis (mm)')
            plt.ylabel(f'{y_axis.upper()}-axis (mm)')
            plt.title(f'Positive Peak Voltage Heatmap\nRange: {vmin_pos:.3f}V to {vmax_pos:.3f}V')
            plt.grid(True, alpha=0.3)
            
            # Add text annotations for data points
            for d in data:
                if d['pos_peak'] is not None:
                    plt.plot(d[x_axis], d[y_axis], 'k.', markersize=2, alpha=0.5)
            
            plt.tight_layout()
            plt.savefig(scan_dir / 'positive_voltage_heatmap.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # Create negative voltage heatmap
        if all_neg_values:
            plt.figure(figsize=(10, 8))
            
            vmin_neg = min(all_neg_values)
            vmax_neg = max(all_neg_values)
            
            # For negative values, invert the colormap so most negative = blue, least negative = red
            im = plt.imshow(neg_grid, 
                          extent=[min(unique_x), max(unique_x), min(unique_y), max(unique_y)],
                          origin='lower', 
                          cmap='coolwarm_r',  # Reversed colormap
                          vmin=vmin_neg, 
                          vmax=vmax_neg,
                          interpolation='nearest')
            
            plt.colorbar(im, label='Voltage (V)')
            plt.xlabel(f'{x_axis.upper()}-axis (mm)')
            plt.ylabel(f'{y_axis.upper()}-axis (mm)')
            plt.title(f'Negative Peak Voltage Heatmap\nRange: {vmin_neg:.3f}V to {vmax_neg:.3f}V\n(Most negative = Blue, Least negative = Red)')
            plt.grid(True, alpha=0.3)
            
            # Add text annotations for data points
            for d in data:
                if d['neg_peak'] is not None:
                    plt.plot(d[x_axis], d[y_axis], 'k.', markersize=2, alpha=0.5)
            
            plt.tight_layout()
            plt.savefig(scan_dir / 'negative_voltage_heatmap.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f"  📊 Created {x_axis.upper()}-{y_axis.upper()} heatmaps:")
        if all_pos_values:
            print(f"    • Positive voltage: {vmin_pos:.3f}V to {vmax_pos:.3f}V")
        if all_neg_values:
            print(f"    • Negative voltage: {vmin_neg:.3f}V to {vmax_neg:.3f}V")

    def automated_scan(self):
        """Interactive setup and execution of automated area scan"""
        print("\n" + "="*70)
        print("AUTOMATED AREA SCAN SETUP")
        print("="*70)
        
        # Show current position
        current_pos = self.hardware.get_current_position()
        print(f"\nCurrent Position: X={current_pos['x']:.3f}mm, Y={current_pos['y']:.3f}mm, Z={current_pos['z']:.3f}mm")
        
        # Get axis configuration
        print("\nAxis Configuration:")
        print("Available axis combinations: x, y, z, xy, xz, yz, xyz")
        axes = input("Enter axis combination (e.g., 'xy' for X-Y scan): ").strip().lower()
        
        if axes not in ['x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz']:
            print("❌ Invalid axis combination")
            return
        
        # Get distances for each axis
        distances = {}
        for axis in axes:
            print(f"\n{axis.upper()}-axis scan distance from current position:")
            try:
                distance = float(input(f"  Distance (mm, + or - for direction): "))
                distances[axis] = distance
                
            except ValueError:
                print("❌ Invalid distance value")
                return
        
        # Get increment
        try:
            increment = float(input(f"\nIncrement step size (mm): "))
            if increment <= 0:
                print("❌ Increment must be positive")
                return
        except ValueError:
            print("❌ Invalid increment value")
            return
        
        # Generate scan points
        points = self.generate_scan_points(axes, distances, increment, current_pos)
        
        print(f"\n📊 Scan Configuration:")
        print(f"  Axes: {axes.upper()}")
        print(f"  Starting position: X={current_pos['x']:.3f}, Y={current_pos['y']:.3f}, Z={current_pos['z']:.3f}")
        for axis, distance in distances.items():
            direction = "positive" if distance >= 0 else "negative"
            print(f"  {axis.upper()}: {distance:+.3f} mm ({direction} direction)")
        print(f"  Increment: {increment:.3f} mm")
        print(f"  Total points: {len(points)}")
        
        # Show scan pattern info
        if axes in ['xy', 'xz', 'yz', 'xyz']:
            print(f"  Scan pattern: Snake/raster (alternating direction per row)")
        
        # Show scan bounds
        if points:
            x_coords = [p['x'] for p in points]
            y_coords = [p['y'] for p in points]
            z_coords = [p['z'] for p in points]
            
            print(f"  Absolute scan bounds:")
            print(f"    X: {min(x_coords):.3f} to {max(x_coords):.3f} mm")
            print(f"    Y: {min(y_coords):.3f} to {max(y_coords):.3f} mm")
            print(f"    Z: {min(z_coords):.3f} to {max(z_coords):.3f} mm")
        
        # Estimate time
        estimated_time = len(points) * 3  # Rough estimate: 3 seconds per point
        print(f"  Estimated time: {estimated_time//60:.0f}m {estimated_time%60:.0f}s")
        
        # Confirm scan
        confirm = input(f"\nProceed with scan? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Scan cancelled")
            return
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scan_dir = Path("scan_data") / timestamp
        scan_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📁 Created scan directory: {scan_dir}")
        
        # Save scan configuration
        config_data = {
            'timestamp': timestamp,
            'axes': axes,
            'starting_position': current_pos,
            'scan_distances': distances,
            'increment': increment,
            'total_points': len(points),
            'scan_pattern': 'snake' if axes in ['xy', 'xz', 'yz', 'xyz'] else 'linear',
            'arduino_config': {
                'port': self.config['hardware']['arduino_port'],
                'steps_per_mm': self.config['hardware']['steps_per_mm']
            },
            'oscilloscope_config': {
                'address': self.config['hardware']['scope_address'],
                'settings': self.scope_settings
            }
        }
        
        with open(scan_dir / 'scan_config.json', 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # Initialize CSV file
        csv_file = scan_dir / 'scan_data.csv'
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['point_num', 'x_mm', 'y_mm', 'z_mm', 'positive_peak_v', 
                           'negative_peak_v', 'peak_to_peak_v', 'method', 'timestamp'])
        
        # Execute scan
        print(f"\n🚀 Starting scan...")
        print("=" * 70)
        
        start_time = time.time()
        successful_points = 0
        
        try:
            for i, point in enumerate(points):
                print(f"\n📍 Point {i+1}/{len(points)}: X={point['x']:.3f}, Y={point['y']:.3f}, Z={point['z']:.3f}")
                
                # Move to position
                if not self.move_to_position(point):
                    print("❌ Failed to move to position")
                    continue
                
                # Wait for stabilization
                time.sleep(0.5)
                
                # Take measurement
                voltage_data = self.sample_voltage_detailed()
                if voltage_data:
                    successful_points += 1
                    
                    # Display measurement
                    pos_peak = voltage_data['positive_peak']
                    neg_peak = voltage_data['negative_peak']
                    vpp = voltage_data['peak_to_peak']
                    method = voltage_data['method']
                    
                    pos_str = f"{pos_peak:+7.3f}V" if pos_peak is not None else "N/A"
                    neg_str = f"{neg_peak:+7.3f}V" if neg_peak is not None else "N/A"
                    vpp_str = f"{vpp:7.3f}V" if vpp is not None else "N/A"
                    
                    print(f"   📊 Pos: {pos_str}, Neg: {neg_str}, VPP: {vpp_str} [{method}]")
                    
                    # Save to CSV
                    with open(csv_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            i+1, point['x'], point['y'], point['z'],
                            pos_peak, neg_peak, vpp, method,
                            datetime.now().isoformat()
                        ])
                else:
                    print("   ❌ No measurement available")
                    
                    # Save empty measurement
                    with open(csv_file, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            i+1, point['x'], point['y'], point['z'],
                            None, None, None, 'FAILED',
                            datetime.now().isoformat()
                        ])
                
                # Progress update
                elapsed = time.time() - start_time
                remaining = (elapsed / (i+1)) * (len(points) - i - 1)
                print(f"   ⏱️  Progress: {((i+1)/len(points)*100):.1f}% | "
                      f"Elapsed: {elapsed//60:.0f}m {elapsed%60:.0f}s | "
                      f"Remaining: {remaining//60:.0f}m {remaining%60:.0f}s")
                
        except KeyboardInterrupt:
            print("\n\n🛑 Scan interrupted by user")
        
        # Generate heatmaps
        self.generate_heatmaps(csv_file, scan_dir, axes)
        
        # Scan complete
        total_time = time.time() - start_time
        print(f"\n" + "="*70)
        print("SCAN COMPLETE")
        print("="*70)
        print(f"Total points: {len(points)}")
        print(f"Successful measurements: {successful_points}")
        print(f"Success rate: {successful_points/len(points)*100:.1f}%")
        print(f"Total time: {total_time//60:.0f}m {total_time%60:.0f}s")
        print(f"Data saved to: {scan_dir}")
        print("="*70)

    def show_status(self):
        """Display current system status"""
        print("\n" + "="*60)
        print("HYDROPHONE SCANNER - ARDUINO & OSCILLOSCOPE CONTROL")
        print("="*60)
        print(f"Arduino Port: {self.config['hardware']['arduino_port']}")
        print(f"Oscilloscope: {'Connected' if self.scope else 'Disconnected'}")
        if self.scope:
            print(f"Scope Address: {self.config['hardware']['scope_address']}")
        print(f"Steps per mm: X={self.config['hardware']['steps_per_mm']['x']}, "
              f"Y={self.config['hardware']['steps_per_mm']['y']}, "
              f"Z={self.config['hardware']['steps_per_mm']['z']}")
        
        current_pos = self.hardware.get_current_position()
        print(f"Current Position: X={current_pos['x']:.3f}mm, "
              f"Y={current_pos['y']:.3f}mm, Z={current_pos['z']:.3f}mm")
        
        if self.scope and self.scope_settings:
            print("\nOscilloscope Settings:")
            for setting, value in self.scope_settings.items():
                if value:
                    print(f"  {setting}: {value}")
        
        print("="*60)

    def move_axis(self, axis: str, distance: float) -> bool:
        """Move specified axis by distance in mm"""
        if axis not in ['x', 'y', 'z']:
            print(f"❌ Invalid axis: {axis}. Must be x, y, or z")
            return False
            
        print(f"Moving {axis.upper()}-axis by {distance:+.3f}mm...")
        
        start_time = time.time()
        success = self.hardware.move_axis(axis, distance)
        end_time = time.time()
        
        if success:
            print(f"✅ Movement completed in {end_time - start_time:.2f}s")
            current_pos = self.hardware.get_current_position()
            print(f"New position: X={current_pos['x']:.3f}mm, "
                  f"Y={current_pos['y']:.3f}mm, Z={current_pos['z']:.3f}mm")
            return True
        else:
            print("❌ Movement failed")
            return False

    def interactive_mode(self):
        """Interactive CLI mode for manual control"""
        print("\n" + "="*60)
        print("INTERACTIVE MOVEMENT & SAMPLING CONTROL")
        print("="*60)
        print("Commands:")
        print("  x+/x-/y+/y-/z+/z- <distance>  - Move axis by distance in mm")
        print("  m                              - Take single voltage measurement")
        print("  sample                         - Start continuous voltage sampling")
        print("  scan                           - Start automated area scan")
        print("  status                         - Show system status")
        print("  r                              - Repeat previous movement")
        print("  help                           - Show this help")
        print("  quit/exit                      - Exit interactive mode")
        print("="*60)
        
        last_movement_cmd = None
        
        while True:
            try:
                cmd = input("\n> ").strip().split()
                if not cmd:
                    continue
                    
                if cmd[0] in ['quit', 'exit', 'q']:
                    break
                    
                elif cmd[0] == 'help':
                    print("\nCommands:")
                    print("  x+/x-/y+/y-/z+/z- <distance>  - Move axis by distance in mm")
                    print("  m                              - Take single voltage measurement")
                    print("  sample                         - Start continuous voltage sampling")
                    print("  scan                           - Start automated area scan")
                    print("  status                         - Show system status")
                    print("  r                              - Repeat previous movement")
                    print("  quit/exit                      - Exit")
                    
                elif cmd[0] == 'r':
                    if last_movement_cmd is None:
                        print("❌ No previous movement command to repeat")
                        continue
                    else:
                        print(f"Repeating: {' '.join(last_movement_cmd)}")
                        cmd = last_movement_cmd
                        
                elif cmd[0] == 'status':
                    self.show_status()
                    continue
                    
                elif cmd[0] == 'm':
                    voltage_data = self.sample_voltage_detailed()
                    if voltage_data:
                        pos_peak = voltage_data['positive_peak']
                        neg_peak = voltage_data['negative_peak']
                        vpp = voltage_data['peak_to_peak']
                        method = voltage_data['method']
                        
                        print(f"📊 Voltage Measurement [{method}]:")
                        if pos_peak is not None:
                            print(f"   Positive Peak: {pos_peak:+7.3f}V")
                        if neg_peak is not None:
                            print(f"   Negative Peak: {neg_peak:+7.3f}V")
                        if vpp is not None:
                            print(f"   Peak-to-Peak:  {vpp:7.3f}V")
                    else:
                        print("❌ Failed to get voltage measurement")
                    continue
                    
                elif cmd[0] == 'sample':
                    self.continuous_sampling()
                    continue
                    
                elif cmd[0] == 'scan':
                    self.automated_scan()
                    continue
                    
                elif len(cmd) == 2 and len(cmd[0]) == 2 and cmd[0][0] in 'xyz' and cmd[0][1] in '+-':
                    # Movement command like x+, y-, z+
                    try:
                        distance = float(cmd[1])
                        axis = cmd[0][0]
                        if cmd[0][1] == '-':
                            distance = -distance
                            
                        if self.move_axis(axis, distance):
                            last_movement_cmd = cmd.copy()
                        
                    except ValueError:
                        print("❌ Invalid distance value")
                        
                else:
                    print("❌ Invalid command. Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Exiting interactive mode...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    def close(self):
        """Clean up hardware connections"""
        print("\n🔌 Closing hardware connections...")
        self.hardware.close()
        if self.scope:
            self.scope.close()
            print("Oscilloscope disconnected")


def main():
    # Initialize controller
    controller = ArduinoController()
    
    try:
        # Show initial status
        controller.show_status()
        
        # Start interactive mode
        controller.interactive_mode()
            
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        controller.close()


if __name__ == '__main__':
    main() 