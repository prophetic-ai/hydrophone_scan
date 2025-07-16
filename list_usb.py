#!/usr/bin/env python3
"""
USB Connection Lister
Lists all USB devices and serial ports on macOS
"""

import subprocess
import sys
import re
from typing import List, Dict

def run_command(cmd: str) -> str:
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Error running command: {e}"

def list_usb_devices() -> List[Dict]:
    """List all USB devices using system_profiler"""
    print("🔍 Scanning USB devices...")
    
    # Get detailed USB information
    usb_info = run_command("system_profiler SPUSBDataType")
    
    devices = []
    current_device = {}
    
    for line in usb_info.split('\n'):
        line = line.strip()
        
        if line.startswith('Product ID:'):
            if current_device:
                devices.append(current_device)
            current_device = {'product_id': line.split(':', 1)[1].strip()}
        elif line.startswith('Vendor ID:'):
            current_device['vendor_id'] = line.split(':', 1)[1].strip()
        elif line.startswith('Version:'):
            current_device['version'] = line.split(':', 1)[1].strip()
        elif line.startswith('Serial Number:'):
            current_device['serial'] = line.split(':', 1)[1].strip()
        elif line.startswith('Manufacturer:'):
            current_device['manufacturer'] = line.split(':', 1)[1].strip()
        elif line.startswith('Location ID:'):
            current_device['location'] = line.split(':', 1)[1].strip()
    
    if current_device:
        devices.append(current_device)
    
    return devices

def list_serial_ports() -> List[str]:
    """List all serial ports using ls command"""
    print("🔍 Scanning serial ports...")
    
    # List all tty devices
    tty_devices = run_command("ls /dev/tty.*")
    usb_devices = run_command("ls /dev/cu.*")
    
    serial_ports = []
    
    # Parse tty devices
    for line in tty_devices.split('\n'):
        if line.strip() and 'tty.' in line:
            serial_ports.append(line.strip())
    
    # Parse cu devices (Callout devices)
    for line in usb_devices.split('\n'):
        if line.strip() and 'cu.' in line:
            serial_ports.append(line.strip())
    
    return serial_ports

def get_device_info(port: str) -> Dict:
    """Get detailed information about a serial port"""
    info = {'port': port, 'type': 'Unknown'}
    
    # Check if it's a USB serial device
    if 'usbmodem' in port or 'usbserial' in port:
        info['type'] = 'USB Serial'
        
        # Try to get more info using ioreg
        ioreg_output = run_command(f"ioreg -p IOUSB -l -w 0 | grep -A 10 -B 10 '{port}'")
        
        # Look for product name
        product_match = re.search(r'"USB Product Name" = "([^"]+)"', ioreg_output)
        if product_match:
            info['product'] = product_match.group(1)
        
        # Look for vendor name
        vendor_match = re.search(r'"USB Vendor Name" = "([^"]+)"', ioreg_output)
        if vendor_match:
            info['vendor'] = vendor_match.group(1)
    
    elif 'Bluetooth' in port:
        info['type'] = 'Bluetooth'
    elif 'modem' in port:
        info['type'] = 'Modem'
    
    return info

def main():
    print("🚀 USB Connection Lister for macOS")
    print("=" * 50)
    
    # List USB devices
    usb_devices = list_usb_devices()
    
    print(f"\n�� Found {len(usb_devices)} USB devices:")
    print("-" * 50)
    
    for i, device in enumerate(usb_devices, 1):
        print(f"\n{i}. USB Device:")
        for key, value in device.items():
            if value:  # Only show non-empty values
                print(f"   {key.replace('_', ' ').title()}: {value}")
    
    # List serial ports
    serial_ports = list_serial_ports()
    
    print(f"\n�� Found {len(serial_ports)} serial ports:")
    print("-" * 50)
    
    for i, port in enumerate(serial_ports, 1):
        info = get_device_info(port)
        print(f"\n{i}. {port}")
        print(f"   Type: {info['type']}")
        if 'product' in info:
            print(f"   Product: {info['product']}")
        if 'vendor' in info:
            print(f"   Vendor: {info['vendor']}")
    
    # Check for your specific devices
    print(f"\n🎯 Looking for your project devices:")
    print("-" * 50)
    
    # Check for Arduino (common patterns)
    arduino_ports = [port for port in serial_ports if 'usbmodem' in port]
    if arduino_ports:
        print(f"✅ Found potential Arduino ports: {arduino_ports}")
    else:
        print("❌ No Arduino-like USB serial ports found")
    
    # Check for oscilloscope (VISA devices)
    try:
        import pyvisa
        rm = pyvisa.ResourceManager()
        visa_devices = rm.list_resources()
        if visa_devices:
            print(f"✅ Found VISA devices: {visa_devices}")
        else:
            print("❌ No VISA devices found")
    except ImportError:
        print("⚠️  PyVISA not installed - cannot check for oscilloscope")
    except Exception as e:
        print(f"⚠️  Error checking VISA devices: {e}")
    
    print(f"\n💡 Tips:")
    print("- Arduino typically appears as /dev/tty.usbmodem* or /dev/cu.usbmodem*")
    print("- Oscilloscopes use VISA addresses like 'USB0::0x0699::0x03A0::*'")
    print("- Use 'ls /dev/tty.*' and 'ls /dev/cu.*' for quick port listing")

if __name__ == "__main__":
    main() 