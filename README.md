# Hydrophone Scanner System
_**A Python Implementation for the Hydrophone — supports automated 1D and 2D scanning patterns with voltage scaling & data visualization.**_

## Getting Started

_Pull the repo and install requirements:_
```bash
git clone https://github.com/prophetic-ai/hydrophone_scan.git
cd hydrophone_scan
pip install -r requirements.txt
```

## Execution Pipeline

**Step 1:** Configure Hardware Settings in 'config.yaml' pre-scan:

```yaml
hardware:
  auto_scaling_enabled: true  # Enable automatic voltage scaling
  arduino_port: '/dev/tty.usbmodem101'  # or 'COMX' for Windows
  scope_address: 'USB0::0xF4EC::0xEE38::SDSMMFCD5R1059::INSTR'  # TEKTRONIX AND SIGLENT SUPPORT
  steps_per_mm:
    x: 100  # 0.01mm per step
    y: 100
    z: 100
  scope_settings:
    trigger_level: 1.0
    vertical_scale: 1.0       # V/div
    horizontal_scale: 2.5e-6  # s/div
    trigger_source: 'EXT'     # EXT or CH1
    trigger_slope: 'RISE'     # RISE or FALL
    trigger_mode: 'AUTO'      # AUTO or NORMAL
    trigger_coupling: 'AC'    # AC or DC
    channel_coupling: 'AC'    # AC or DC
    channel_position: 0       # vertical position
    acquisition_mode: 'AVERAGE'  # SAMPLE, AVERAGE, PEAKDETECT
    average_count: 16         # 4, 16, 32, 64, 128 when mode is AVERAGE

scan:
  type: '2d_xy'  # 1d_x, 1d_y, 1d_z, 2d_xy, 2d_xz, 2d_yz
  dimensions:
    x: 20  # mm
    y: 20  # mm 
    z: 0   # mm
    resolution: 0.5  # mm
  calibration_value: 0.3112  # V/MPa
  base_path: './scan_data'
  save_options:
    save_waveforms: true     # Enable/disable saving of waveforms
    waveform_decimation: 1   # Save every Nth waveform (1 = all)
```

**Step 2:** Run Scanner:

```python
python main.py
```

**Step 3:** Use the Interactive Menu System:

The scanner now features a streamlined menu interface with the following options:
1. Enter positioning mode
2. Reload config
3. Start scan
4. Exit

During positioning mode, use these commands:
```
x+/- <mm>  : Move in X
y+/- <mm>  : Move in Y  
z+/- <mm>  : Move in Z
m          : Measure voltage at current position
w          : View current waveform
done       : Return to main menu
```

**Step 4:** After Positioning and Starting Scan, the System Will:
- Use the current position as center point
- Execute the scan pattern defined in config.yaml
- Auto-scale voltage measurements (controlled by auto_scaling_enabled)
- Generate pressure maps and analysis
- Return to start position
- Display interactive plots of results

**Scan Output:**
Results are saved with timestamp in scan_data/:

- Raw voltage measurements and scan metadata
- Complete waveform data (optional, controlled by save_options)
- Pressure maps (positive and negative peaks)
- FWHM calculations when applicable
- Updated configuration file with scan center position

