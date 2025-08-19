#!/usr/bin/env python3
"""
Test script to verify motor direction consistency after Arduino fix
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_controller import MotorController
from config import load_config
import time

def test_motor_directions():
    """Test that all axes move in the expected directions"""
    print("=== Motor Direction Consistency Test ===")
    
    # Load config and initialize motor controller
    config = load_config('config.yaml')
    motor_controller = MotorController(
        arduino_port=config['hardware']['arduino_port'],
        config=config
    )
    
    try:
        # Get starting position
        start_pos = motor_controller.get_current_position()
        print(f"Starting position: X={start_pos['x']:.3f}, Y={start_pos['y']:.3f}, Z={start_pos['z']:.3f}")
        
        # Test small movements in each direction
        test_distance = 1.0  # 1mm test movements
        
        print(f"\nTesting +{test_distance}mm movements:")
        
        # Test X+ movement
        print(f"Moving X+ {test_distance}mm...")
        motor_controller.move_axis('x', test_distance)
        pos1 = motor_controller.get_current_position()
        x_moved = pos1['x'] - start_pos['x']
        print(f"X moved: {x_moved:+.3f}mm (expected: +{test_distance:.3f}mm)")
        
        # Test Y+ movement  
        print(f"Moving Y+ {test_distance}mm...")
        motor_controller.move_axis('y', test_distance)
        pos2 = motor_controller.get_current_position()
        y_moved = pos2['y'] - pos1['y']
        print(f"Y moved: {y_moved:+.3f}mm (expected: +{test_distance:.3f}mm)")
        
        # Test Z+ movement
        print(f"Moving Z+ {test_distance}mm...")
        motor_controller.move_axis('z', test_distance)
        pos3 = motor_controller.get_current_position()
        z_moved = pos3['z'] - pos2['z']
        print(f"Z moved: {z_moved:+.3f}mm (expected: +{test_distance:.3f}mm)")
        
        print(f"\nTesting -{test_distance}mm movements:")
        
        # Test X- movement
        print(f"Moving X- {test_distance}mm...")
        motor_controller.move_axis('x', -test_distance)
        pos4 = motor_controller.get_current_position()
        x_moved_back = pos4['x'] - pos3['x']
        print(f"X moved: {x_moved_back:+.3f}mm (expected: -{test_distance:.3f}mm)")
        
        # Test Y- movement
        print(f"Moving Y- {test_distance}mm...")
        motor_controller.move_axis('y', -test_distance)
        pos5 = motor_controller.get_current_position()
        y_moved_back = pos5['y'] - pos4['y']
        print(f"Y moved: {y_moved_back:+.3f}mm (expected: -{test_distance:.3f}mm)")
        
        # Test Z- movement
        print(f"Moving Z- {test_distance}mm...")
        motor_controller.move_axis('z', -test_distance)
        pos6 = motor_controller.get_current_position()
        z_moved_back = pos6['z'] - pos5['z']
        print(f"Z moved: {z_moved_back:+.3f}mm (expected: -{test_distance:.3f}mm)")
        
        # Check if we're back at starting position
        final_pos = motor_controller.get_current_position()
        print(f"\nFinal position: X={final_pos['x']:.3f}, Y={final_pos['y']:.3f}, Z={final_pos['z']:.3f}")
        
        # Calculate total errors
        x_error = abs(final_pos['x'] - start_pos['x'])
        y_error = abs(final_pos['y'] - start_pos['y'])
        z_error = abs(final_pos['z'] - start_pos['z'])
        
        print(f"Position errors: X={x_error:.3f}mm, Y={y_error:.3f}mm, Z={z_error:.3f}mm")
        
        # Evaluate results
        tolerance = 0.1  # 0.1mm tolerance
        if x_error < tolerance and y_error < tolerance and z_error < tolerance:
            print("✅ Direction test PASSED - All axes move consistently")
        else:
            print("❌ Direction test FAILED - Check motor wiring/direction")
            
        # Test the specific YX scan pattern issue
        print(f"\n=== YX Snake Pattern Test ===")
        print("Testing the pattern that caused the original issue...")
        
        # Move to a known position
        test_pos = {'x': 0.0, 'y': 0.0, 'z': final_pos['z']}
        motor_controller.move_to_position(test_pos)
        
        # Simulate the problematic sequence: Y=0 → Y=-2 → X=+2 → Y=0
        positions = [
            {'x': 0.0, 'y': 0.0, 'z': test_pos['z']},    # Start
            {'x': 0.0, 'y': -2.0, 'z': test_pos['z']},   # Y down
            {'x': 2.0, 'y': -2.0, 'z': test_pos['z']},   # X right  
            {'x': 2.0, 'y': 0.0, 'z': test_pos['z']},    # Y up (this was failing)
        ]
        
        for i, pos in enumerate(positions):
            print(f"Moving to position {i+1}: X={pos['x']:.1f}, Y={pos['y']:.1f}")
            success = motor_controller.move_to_position(pos)
            actual_pos = motor_controller.get_current_position()
            
            x_error = abs(actual_pos['x'] - pos['x'])
            y_error = abs(actual_pos['y'] - pos['y'])
            
            if success and x_error < tolerance and y_error < tolerance:
                print(f"✅ Position {i+1} reached successfully")
            else:
                print(f"❌ Position {i+1} FAILED - Expected: X={pos['x']:.1f}, Y={pos['y']:.1f}, Got: X={actual_pos['x']:.1f}, Y={actual_pos['y']:.1f}")
                break
        else:
            print("✅ YX snake pattern test PASSED")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        
    finally:
        motor_controller.close()
        print("\n=== Test Complete ===")

if __name__ == '__main__':
    test_motor_directions() 