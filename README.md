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
  type: '2d_xy'  # 1d_x, 1d_y, 1d_z, 2d_xy, 2d_yx, 2d_xz, 2d_yz
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

**Voltage-to-Pressure Conversion:**
The system automatically converts voltage measurements to pressure using the `calibration_value` specified in config.yaml:
- Pressure (MPa) = Voltage (V) / calibration_value (V/MPa)
- Current calibration value: 0.2743 V/MPa
- Both voltage and pressure values are displayed during measurements and saved in reports
- Separate heatmaps are generated for both voltage and pressure measurements

**Scan Patterns:**
The system supports different scan patterns with optimized movement orders:
- **1D scans** (1d_x, 1d_y, 1d_z): Linear movement along single axis
- **2D scans**: Snake/raster pattern for efficient scanning
  - **2d_xy**: X is primary axis, Y is secondary (scan X first, then move Y)
  - **2d_yx**: Y is primary axis, X is secondary (scan Y first, then move X)
  - **2d_xz**: X is primary axis, Z is secondary
  - **2d_yz**: Y is primary axis, Z is secondary
- **3D scans** (xyz): 3D snake pattern with alternating directions