#!/usr/bin/env python3
"""
Debug script to analyze heatmap distortion issues
"""

import csv
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def analyze_scan_data(csv_file_path):
    """Analyze scan data to identify heatmap issues"""
    
    print("🔍 Analyzing scan data for heatmap distortion...")
    print("=" * 60)
    
    # Read the CSV data
    data = []
    with open(csv_file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['method'] != 'FAILED':
                try:
                    data.append({
                        'point_num': int(row['point_num']),
                        'x': float(row['x_mm']),
                        'y': float(row['y_mm']),
                        'z': float(row['z_mm']),
                        'pos_peak': float(row['positive_peak_v']) if row['positive_peak_v'] and row['positive_peak_v'] != 'None' else None,
                        'neg_peak': float(row['negative_peak_v']) if row['negative_peak_v'] and row['negative_peak_v'] != 'None' else None
                    })
                except (ValueError, TypeError):
                    continue
    
    print(f"📊 Total data points: {len(data)}")
    
    # Analyze coordinates
    x_coords = [d['x'] for d in data]
    y_coords = [d['y'] for d in data]
    
    print(f"\n📍 Coordinate Analysis:")
    print(f"  X range: {min(x_coords):.3f} to {max(x_coords):.3f} mm")
    print(f"  Y range: {min(y_coords):.3f} to {max(y_coords):.3f} mm")
    print(f"  Unique X values: {sorted(set(x_coords))}")
    print(f"  Unique Y values: {sorted(set(y_coords))}")
    
    # Check for expected grid pattern
    unique_x = sorted(set(x_coords))
    unique_y = sorted(set(y_coords))
    expected_points = len(unique_x) * len(unique_y)
    
    print(f"\n🔧 Grid Analysis:")
    print(f"  Expected grid: {len(unique_x)} x {len(unique_y)} = {expected_points} points")
    print(f"  Actual points: {len(data)}")
    print(f"  Match: {'✅' if len(data) == expected_points else '❌'}")
    
    # Check scan order and pattern
    print(f"\n📋 Scan Pattern Analysis:")
    print("  First 10 points:")
    for i in range(min(10, len(data))):
        d = data[i]
        print(f"    Point {d['point_num']}: X={d['x']:.3f}, Y={d['y']:.3f}")
    
    # Check for missing data points
    missing_points = []
    for x in unique_x:
        for y in unique_y:
            found = False
            for d in data:
                if abs(d['x'] - x) < 0.001 and abs(d['y'] - y) < 0.001:
                    found = True
                    break
            if not found:
                missing_points.append((x, y))
    
    if missing_points:
        print(f"\n⚠️  Missing data points: {len(missing_points)}")
        for x, y in missing_points[:5]:  # Show first 5
            print(f"    Missing: X={x:.3f}, Y={y:.3f}")
        if len(missing_points) > 5:
            print(f"    ... and {len(missing_points) - 5} more")
    
    # Check for coordinate precision issues
    print(f"\n🔍 Coordinate Precision Check:")
    x_diffs = []
    y_diffs = []
    
    for i in range(len(unique_x) - 1):
        x_diffs.append(unique_x[i+1] - unique_x[i])
    for i in range(len(unique_y) - 1):
        y_diffs.append(unique_y[i+1] - unique_y[i])
    
    if x_diffs:
        print(f"  X increments: {x_diffs}")
        print(f"  X increment consistency: {'✅' if len(set([round(d, 6) for d in x_diffs])) == 1 else '❌'}")
    
    if y_diffs:
        print(f"  Y increments: {y_diffs}")
        print(f"  Y increment consistency: {'✅' if len(set([round(d, 6) for d in y_diffs])) == 1 else '❌'}")
    
    # Analyze voltage data
    pos_peaks = [d['pos_peak'] for d in data if d['pos_peak'] is not None]
    neg_peaks = [d['neg_peak'] for d in data if d['neg_peak'] is not None]
    
    print(f"\n📊 Voltage Data Analysis:")
    if pos_peaks:
        print(f"  Positive peaks: {len(pos_peaks)} values")
        print(f"    Range: {min(pos_peaks):.6f}V to {max(pos_peaks):.6f}V")
        print(f"    Mean: {np.mean(pos_peaks):.6f}V")
    
    if neg_peaks:
        print(f"  Negative peaks: {len(neg_peaks)} values")
        print(f"    Range: {min(neg_peaks):.6f}V to {max(neg_peaks):.6f}V")
        print(f"    Mean: {np.mean(neg_peaks):.6f}V")
    
    # Create diagnostic plots
    print(f"\n📈 Creating diagnostic plots...")
    
    # Plot 1: Scan path visualization
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    plt.plot(x_coords, y_coords, 'b-', alpha=0.5, linewidth=1)
    plt.plot(x_coords, y_coords, 'ro', markersize=3)
    
    # Number the first few points to show scan order
    for i in range(min(20, len(data))):
        plt.annotate(str(i+1), (x_coords[i], y_coords[i]), 
                    xytext=(5, 5), textcoords='offset points', fontsize=8)
    
    plt.xlabel('X (mm)')
    plt.ylabel('Y (mm)')
    plt.title('Scan Path and Order')
    plt.grid(True, alpha=0.3)
    plt.axis('equal')
    
    # Plot 2: Negative peak heatmap recreation
    plt.subplot(1, 2, 2)
    
    if neg_peaks:
        # Create grid manually to debug
        grid = np.full((len(unique_y), len(unique_x)), np.nan)
        x_to_idx = {x: i for i, x in enumerate(unique_x)}
        y_to_idx = {y: i for i, y in enumerate(unique_y)}
        
        for d in data:
            if d['neg_peak'] is not None:
                x_idx = x_to_idx[d['x']]
                y_idx = y_to_idx[d['y']]
                grid[y_idx, x_idx] = d['neg_peak']
        
        extent = (min(unique_x), max(unique_x), min(unique_y), max(unique_y))
        im = plt.imshow(grid, extent=extent, origin='lower', 
                       cmap='RdYlBu_r', interpolation='nearest')
        plt.colorbar(im, label='Negative Peak (V)')
        plt.xlabel('X (mm)')
        plt.ylabel('Y (mm)')
        plt.title('Negative Peak Heatmap (Debug)')
        plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('scan_debug_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\n✅ Analysis complete! Debug plot saved as 'scan_debug_analysis.png'")

def main():
    # Look for the most recent scan data
    scan_data_dir = Path("scan_data")
    if not scan_data_dir.exists():
        print("❌ No scan_data directory found")
        return
    
    # Find most recent scan
    scan_dirs = [d for d in scan_data_dir.iterdir() if d.is_dir()]
    if not scan_dirs:
        print("❌ No scan directories found")
        return
    
    latest_scan = max(scan_dirs, key=lambda d: d.name)
    csv_file = latest_scan / "scan_data.csv"
    
    if not csv_file.exists():
        print(f"❌ No scan_data.csv found in {latest_scan}")
        return
    
    print(f"📁 Analyzing scan data from: {latest_scan}")
    analyze_scan_data(csv_file)

if __name__ == '__main__':
    main() 