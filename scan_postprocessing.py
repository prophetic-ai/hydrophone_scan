"""
Scan Post-processing for Hydrophone Scanner
Handles data visualization and analysis of scan results.
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Optional


class ScanPostProcessor:
    
    def __init__(self):
        pass
    
    def generate_heatmaps(self, csv_file: Path, scan_dir: Path, axes: str) -> None:
        """Generate heatmap visualizations from scan data"""
        try:
            print(f"\n📊 Generating heatmaps...")
            
            # Read CSV data
            data = self._read_scan_data(csv_file)
            
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
    
    def _read_scan_data(self, csv_file: Path) -> List[Dict[str, Optional[float]]]:
        """Read and parse scan data from CSV file"""
        data = []
        
        try:
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
        except Exception as e:
            print(f"❌ Error reading scan data: {e}")
            
        return data

    def _create_2d_heatmap(self, data: List[Dict[str, Optional[float]]], x_axis: str, y_axis: str, scan_dir: Path) -> None:
        """Create 2D heatmaps for positive and negative voltage peaks"""
        
        # Extract coordinates and voltage data, filtering out None values
        x_coords: List[float] = [float(d[x_axis]) for d in data if d[x_axis] is not None]
        y_coords: List[float] = [float(d[y_axis]) for d in data if d[y_axis] is not None]
        pos_peaks: List[float] = [float(d['pos_peak']) for d in data if d['pos_peak'] is not None]
        neg_peaks: List[float] = [float(d['neg_peak']) for d in data if d['neg_peak'] is not None]
        
        if not pos_peaks and not neg_peaks:
            print("⚠️  No valid voltage data for heatmap generation")
            return
        
        # Get unique coordinates for grid (already filtered for None values)
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
            x_val = d[x_axis]
            y_val = d[y_axis]
            if x_val is not None and y_val is not None:
                x_idx = x_to_idx[x_val]
                y_idx = y_to_idx[y_val]
                
                if d['pos_peak'] is not None:
                    pos_grid[y_idx, x_idx] = d['pos_peak']
                if d['neg_peak'] is not None:
                    neg_grid[y_idx, x_idx] = d['neg_peak']
        
        # Calculate global min/max for consistent color scaling
        all_pos_values = [v for v in pos_peaks if not np.isnan(v)]
        all_neg_values = [v for v in neg_peaks if not np.isnan(v)]
        
        # Create positive voltage heatmap
        if all_pos_values:
            self._create_heatmap_plot(
                pos_grid, unique_x, unique_y, all_pos_values, 
                x_axis, y_axis, 'positive', scan_dir, data
            )
        
        # Create negative voltage heatmap
        if all_neg_values:
            self._create_heatmap_plot(
                neg_grid, unique_x, unique_y, all_neg_values, 
                x_axis, y_axis, 'negative', scan_dir, data
            )
        
        print(f"  📊 Created {x_axis.upper()}-{y_axis.upper()} heatmaps:")
        if all_pos_values:
            print(f"    • Positive voltage: {min(all_pos_values):.3f}V to {max(all_pos_values):.3f}V")
        if all_neg_values:
            print(f"    • Negative voltage: {min(all_neg_values):.3f}V to {max(all_neg_values):.3f}V")
    
    def _create_heatmap_plot(self, grid: np.ndarray, unique_x: List[float], unique_y: List[float], 
                           values: List[float], x_axis: str, y_axis: str, voltage_type: str, 
                           scan_dir: Path, data: List[Dict[str, Optional[float]]]) -> None:
        """Create a single heatmap plot"""
        plt.figure(figsize=(10, 8))
        
        vmin = min(values)
        vmax = max(values)
        
        # Choose colormap based on voltage type
        if voltage_type == 'negative':
            # For negative values, invert the colormap so most negative = blue, least negative = red
            cmap = 'coolwarm_r'
            title_suffix = f"\nRange: {vmin:.3f}V to {vmax:.3f}V\n(Most negative = Blue, Least negative = Red)"
        else:
            cmap = 'coolwarm'
            title_suffix = f"\nRange: {vmin:.3f}V to {vmax:.3f}V"
        
        # Create extent as tuple for proper type handling
        extent = (min(unique_x), max(unique_x), min(unique_y), max(unique_y))
        
        im = plt.imshow(grid, 
                      extent=extent,
                      origin='lower', 
                      cmap=cmap,
                      vmin=vmin, 
                      vmax=vmax,
                      interpolation='nearest')
        
        plt.colorbar(im, label='Voltage (V)')
        plt.xlabel(f'{x_axis.upper()}-axis (mm)')
        plt.ylabel(f'{y_axis.upper()}-axis (mm)')
        plt.title(f'{voltage_type.capitalize()} Peak Voltage Heatmap{title_suffix}')
        plt.grid(True, alpha=0.3)
        
        # Add text annotations for data points
        peak_key = 'pos_peak' if voltage_type == 'positive' else 'neg_peak'
        for d in data:
            if d[peak_key] is not None and d[x_axis] is not None and d[y_axis] is not None:
                plt.plot(d[x_axis], d[y_axis], 'k.', markersize=2, alpha=0.5)
        
        plt.tight_layout()
        plt.savefig(scan_dir / f'{voltage_type}_voltage_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_summary_report(self, csv_file: Path, scan_dir: Path, scan_config: Dict) -> None:
        """Generate a summary report of the scan results"""
        try:
            data = self._read_scan_data(csv_file)
            
            if not data:
                print("⚠️  No data for summary report")
                return
            
            # Calculate statistics
            pos_peaks = [d['pos_peak'] for d in data if d['pos_peak'] is not None]
            neg_peaks = [d['neg_peak'] for d in data if d['neg_peak'] is not None]
            
            report_lines = []
            report_lines.append("HYDROPHONE SCAN SUMMARY REPORT")
            report_lines.append("=" * 50)
            report_lines.append(f"Scan Date: {scan_config.get('timestamp', 'Unknown')}")
            report_lines.append(f"Axes: {scan_config.get('axes', 'Unknown')}")
            report_lines.append(f"Total Points: {len(data)}")
            report_lines.append(f"Increment: {scan_config.get('increment', 'Unknown')} mm")
            report_lines.append("")
            
            if pos_peaks:
                report_lines.append("POSITIVE PEAK STATISTICS:")
                report_lines.append(f"  Count: {len(pos_peaks)}")
                report_lines.append(f"  Min: {min(pos_peaks):.6f} V")
                report_lines.append(f"  Max: {max(pos_peaks):.6f} V")
                report_lines.append(f"  Mean: {np.mean(pos_peaks):.6f} V")
                report_lines.append(f"  Std Dev: {np.std(pos_peaks):.6f} V")
                report_lines.append("")
            
            if neg_peaks:
                report_lines.append("NEGATIVE PEAK STATISTICS:")
                report_lines.append(f"  Count: {len(neg_peaks)}")
                report_lines.append(f"  Min: {min(neg_peaks):.6f} V")
                report_lines.append(f"  Max: {max(neg_peaks):.6f} V")
                report_lines.append(f"  Mean: {np.mean(neg_peaks):.6f} V")
                report_lines.append(f"  Std Dev: {np.std(neg_peaks):.6f} V")
                report_lines.append("")
            
            # Write report
            report_file = scan_dir / 'scan_summary.txt'
            with open(report_file, 'w') as f:
                f.write('\n'.join(report_lines))
            
            print(f"✅ Summary report saved to {report_file}")
            
        except Exception as e:
            print(f"❌ Error generating summary report: {e}")
    
    def export_data_formats(self, csv_file: Path, scan_dir: Path) -> None:
        """Export data in additional formats (JSON, numpy arrays)"""
        try:
            data = self._read_scan_data(csv_file)
            
            if not data:
                print("⚠️  No data to export")
                return
            
            # Export as JSON
            import json
            json_file = scan_dir / 'scan_data.json'
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Export as numpy arrays - filter out None values
            if data:
                x_coords = np.array([d['x'] for d in data if d['x'] is not None])
                y_coords = np.array([d['y'] for d in data if d['y'] is not None])
                z_coords = np.array([d['z'] for d in data if d['z'] is not None])
                pos_peaks = np.array([d['pos_peak'] for d in data if d['pos_peak'] is not None])
                neg_peaks = np.array([d['neg_peak'] for d in data if d['neg_peak'] is not None])
                
                np.savez(scan_dir / 'scan_arrays.npz',
                        x=x_coords, y=y_coords, z=z_coords,
                        positive_peaks=pos_peaks, negative_peaks=neg_peaks)
            
            print(f"✅ Data exported to additional formats in {scan_dir}")
            
        except Exception as e:
            print(f"❌ Error exporting data: {e}") 