#!/usr/bin/env python3
"""
Hydrophone Scanner Controller
Provides command-line interface for controlling the hydrophone scanner movements,
sampling voltage data from the oscilloscope, and performing automated area scans
"""

import sys
import os
import time
import numpy as np
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add the current directory to Python path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_controller import MotorController
from oscilloscope_reader import OscilloscopeReader
from scan_postprocessing import ScanPostProcessor
from config import load_config

class Scanner:
    def __init__(self, config_path: str = 'config.yaml'):
        """Initialize hydrophone scanner with configuration"""
        try:
            self.config = load_config(config_path)
            print(f"✅ Loaded configuration from {config_path}")
            
            # Initialize motor controller (Arduino-based)
            self.motor_controller = MotorController(
                arduino_port=self.config['hardware']['arduino_port'],
                config=self.config
            )
            
            # Initialize oscilloscope reader
            scope_address = self.config['hardware']['scope_address']
            self.oscilloscope = OscilloscopeReader(scope_address) if scope_address else None
            
            # Initialize post-processor
            self.post_processor = ScanPostProcessor()
            
            print("✅ Hydrophone scanner initialized successfully")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            sys.exit(1)

    def sample_voltage_detailed(self) -> Optional[Dict]:
        """Sample voltage with detailed breakdown using oscilloscope reader"""
        if not self.oscilloscope:
            print("❌ Oscilloscope not connected")
            return None
        
        return self.oscilloscope.sample_voltage_detailed()

    def continuous_sampling(self):
        """Continuous voltage sampling mode"""
        if not self.oscilloscope:
            print("❌ Oscilloscope not connected - cannot sample voltage")
            return
        
        self.oscilloscope.continuous_sampling()

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
        return self.motor_controller.move_to_position(target_position)

    def generate_heatmaps(self, csv_file: Path, scan_dir: Path, axes: str):
        """Generate heatmap visualizations from scan data"""
        self.post_processor.generate_heatmaps(csv_file, scan_dir, axes)

    def automated_scan(self):
        """Interactive setup and execution of automated area scan"""
        print("\n" + "="*70)
        print("AUTOMATED AREA SCAN SETUP")
        print("="*70)
        
        # Show current position
        current_pos = self.motor_controller.get_current_position()
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
                'settings': self.oscilloscope.get_settings() if self.oscilloscope else {}
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
        
        # Generate additional analysis
        self.post_processor.generate_summary_report(csv_file, scan_dir, config_data)
        self.post_processor.export_data_formats(csv_file, scan_dir)
        
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
        print("HYDROPHONE SCANNER STATUS")
        print("="*60)
        print(f"Arduino Port: {self.config['hardware']['arduino_port']}")
        print(f"Oscilloscope: {'Connected' if self.oscilloscope else 'Disconnected'}")
        if self.oscilloscope:
            print(f"Scope Address: {self.config['hardware']['scope_address']}")
        print(f"Steps per mm: X={self.config['hardware']['steps_per_mm']['x']}, "
              f"Y={self.config['hardware']['steps_per_mm']['y']}, "
              f"Z={self.config['hardware']['steps_per_mm']['z']}")
        
        current_pos = self.motor_controller.get_current_position()
        print(f"Current Position: X={current_pos['x']:.3f}mm, "
              f"Y={current_pos['y']:.3f}mm, Z={current_pos['z']:.3f}mm")
        
        if self.oscilloscope and self.oscilloscope.get_settings():
            print("\nOscilloscope Settings:")
            for setting, value in self.oscilloscope.get_settings().items():
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
        success = self.motor_controller.move_axis(axis, distance)
        end_time = time.time()
        
        if success:
            print(f"✅ Movement completed in {end_time - start_time:.2f}s")
            current_pos = self.motor_controller.get_current_position()
            print(f"New position: X={current_pos['x']:.3f}mm, "
                  f"Y={current_pos['y']:.3f}mm, Z={current_pos['z']:.3f}mm")
            return True
        else:
            print("❌ Movement failed")
            return False

    def interactive_mode(self):
        """Interactive CLI mode for manual control"""
        print("\n" + "="*60)
        print("INTERACTIVE SCANNER CONTROL")
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
        print("\n🔌 Closing scanner connections...")
        self.motor_controller.close()
        if self.oscilloscope:
            self.oscilloscope.close()


def main():
    # Initialize scanner
    scanner = Scanner()
    
    try:
        # Show initial status
        scanner.show_status()
        
        # Start interactive mode
        scanner.interactive_mode()
            
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        scanner.close()


if __name__ == '__main__':
    main() 