#!/usr/bin/env python3
"""
Test script for motor enable/disable functionality
"""

import sys
import os
import time

# Add the current directory to Python path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_controller import MotorController
from config import load_config

def test_motor_control():
    """Test basic motor control functionality"""
    config = load_config()
    
    # Get Arduino port from config
    arduino_port = config['hardware']['arduino_port']
    
    # Initialize hardware controller
    hw = MotorController(arduino_port=arduino_port, config=config)
    
    print("Testing motor control functionality...")
    print("=" * 50)
    
    # Test 1: Manual enable/disable
    print("\n1. Testing manual motor enable/disable:")
    print("   - Motors should be disabled (quiet) at startup")
    time.sleep(2)
    
    print("   - Enabling motors (you should hear a slight click/hum)")
    hw.enable_motors()
    time.sleep(3)
    
    print("   - Disabling motors (noise should stop)")
    hw.disable_motors()
    time.sleep(2)
    
    # Test 2: Movement with automatic enable/disable
    print("\n2. Testing movement with automatic motor control:")
    print("   - Moving X axis 10mm (motors will auto-enable then disable)")
    hw.move_axis('x', 10.0)
    time.sleep(2)
    
    print("   - Moving Y axis 5mm")
    hw.move_axis('y', 5.0)
    time.sleep(2)
    
    print("   - Moving back to origin")
    hw.move_axis('x', -10.0)
    time.sleep(1)
    hw.move_axis('y', -5.0)
    time.sleep(2)
    
    print("\n3. Motor noise test:")
    print("   - Motors should be quiet now (disabled)")
    print("   - Listen for any motor noise...")
    time.sleep(5)
    
    print("\nTest complete! Motors should be disabled and quiet.")
    
    # Clean up
    hw.close()

if __name__ == "__main__":
    test_motor_control() 