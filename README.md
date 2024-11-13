# Hydrophone Scanner System
_**A Python Implementation for the Hydrophone — supports automated 1D and 2D scanning patterns with voltage scaling & data visualization.**_


## Execution Pipeline

**Step 1:** Configure Hardware Settings in 'config.yaml' pre-scan:

```yaml
hardware:
  arduino_port: '/dev/tty.usbmodem101'  # or 'COMX' for Windows
  scope_address: 'USB0::0xF4EC::0xEE38::SDSMMFCD5R1059::INSTR' # TEKTRONIX AND SIGLENT SUPPORT
  steps_per_mm:
    x: 100  # 0.01mm per step
    y: 100
    z: 100

scan:
  type: '2d_xy'  # 1d_x, 1d_y, 1d_z, 2d_xy, 2d_xz, 2d_yz
  dimensions:
    x: 20  # mm
    y: 20  # mm 
    z: 0   # mm
    resolution: 0.5  # mm
  calibration_value: 0.3112  # V/MPa
```

**Step 2:** Run Scanner:

```python
python main.py
```

Similar to how we interfaced with the MATLAB GUI, _**manual movement mode will start first**_. Use the following commands to position hydrophone at peak pressure/estimated geometric center:
```
x+/- <mm>  : Move in X
y+/- <mm>  : Move in Y  
z+/- <mm>  : Move in Z
m          : Measure voltage at current position
done       : Finish positioning
```

**Step 3:** Once positioned and 'done' entered, the scanner code will:
- Use the current position at center point
- Execute the scan pattern defined in config.yaml
- Auto-scale voltage measurements (to avoid clipping & optimize snr)
- Generate pressure maps and analysis
- Return to start position


**Scan Output:**
Results are saved with timestamp in scan_data/:

- Raw voltage measurements and scan metadata
- Pressure maps (positive and negative peaks)
- FWHM calculations when applicable

