#!/usr/bin/env python3
"""
Simple voltage sampling from Siglent oscilloscope with robust USB handling
"""

import pyvisa
import time
import numpy as np
import warnings

def sample_voltage_robust():
    """Robust voltage sampling with USB error handling"""
    
    siglent_address = "USB0::62700::60984::SDSMMFCD5R1059::0::INSTR"
    
    try:
        # Suppress the USB firmware warning
        warnings.filterwarnings("ignore", category=UserWarning, module="pyvisa_py")
        
        rm = pyvisa.ResourceManager()
        scope = rm.open_resource(siglent_address)
        scope.timeout = 15000  # Longer timeout for USB issues
        
        print("🔗 Connecting to Siglent oscilloscope...")
        
        # More robust connection with retries
        connected = False
        for attempt in range(3):
            try:
                scope.write('CHDR OFF')
                time.sleep(0.5)
                
                # Test basic communication
                idn = scope.query('*IDN?')
                print(f"✅ Connected: {idn.strip()}")
                connected = True
                break
                
            except Exception as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        if not connected:
            print("❌ Could not establish stable connection")
            return
        
        # Read current settings with error handling
        print("📋 Reading current oscilloscope settings...")
        settings = {}
        
        setting_queries = {
            'vdiv': 'C1:VDIV?',
            'tdiv': 'TDIV?',
            'coupling': 'C1:CPL?',
            'trigger_mode': 'TRMD?',
            'offset': 'C1:OFST?'
        }
        
        for setting, query in setting_queries.items():
            try:
                response = scope.query(query)
                settings[setting] = response.strip()
                print(f"  {setting}: {response.strip()}")
            except Exception as e:
                print(f"  ⚠️  Could not read {setting}: {e}")
                settings[setting] = None
        
        print("✅ Settings read")
        print("\n📊 Sampling voltage (Press Ctrl+C to stop):")
        print("=" * 70)
        
        sample_count = 0
        consecutive_errors = 0
        
        while True:
            try:
                # Method 1: Try to get measurements using simpler commands
                success = False
                
                # Try different measurement approaches
                measurement_methods = [
                    ('PAVA', 'C1:PAVA? PKPK'),
                    ('MEAS', 'MEAS:VAMP? C1'),
                    ('PARAMETER', 'PARA? C1,PKPK')
                ]
                
                for method_name, command in measurement_methods:
                    try:
                        response = scope.query(command)
                        print(f"Debug [{method_name}]: {repr(response)}")
                        
                        # Parse different response formats
                        if ',' in response:
                            # Format: "PARAMETER,VALUE"
                            value_str = response.split(',')[1].strip()
                            value = float(value_str.rstrip('V'))
                            
                            sample_count += 1
                            print(f"Sample {sample_count:4d}: Peak-to-Peak = {value:+7.3f}V")
                            success = True
                            break
                            
                        elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                            # Direct numeric response
                            value = float(response.strip())
                            sample_count += 1
                            print(f"Sample {sample_count:4d}: Measurement = {value:+7.3f}V")
                            success = True
                            break
                            
                    except Exception as e:
                        print(f"  {method_name} method failed: {e}")
                        continue
                
                # Method 2: If measurements fail, try waveform approach
                if not success:
                    print("Trying waveform method...")
                    try:
                        # Simple waveform query
                        scope.write('C1:WF? DAT1')
                        time.sleep(0.5)  # Give more time for USB
                        
                        raw_data = scope.read_raw()
                        
                        if len(raw_data) > 10:
                            print(f"Got {len(raw_data)} bytes of waveform data")
                            
                            # Try to extract some basic info
                            if settings['vdiv']:
                                try:
                                    vdiv_val = float(settings['vdiv'].split()[-1].strip('V'))
                                    print(f"Current scale: {vdiv_val}V/div")
                                    sample_count += 1
                                    print(f"Sample {sample_count:4d}: Waveform acquired ({len(raw_data)} bytes)")
                                    success = True
                                except:
                                    pass
                        
                    except Exception as e:
                        print(f"Waveform method failed: {e}")
                
                if success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    print(f"⚠️  No measurement available (error count: {consecutive_errors})")
                    
                    if consecutive_errors > 5:
                        print("Too many consecutive errors - trying to reconnect...")
                        scope.close()
                        time.sleep(2)
                        scope = rm.open_resource(siglent_address)
                        scope.timeout = 15000
                        consecutive_errors = 0
                
                time.sleep(1)  # Slower sampling to reduce USB stress
                
            except KeyboardInterrupt:
                print("\n\n🛑 Sampling stopped by user")
                break
            except Exception as e:
                print(f"Sampling error: {e}")
                consecutive_errors += 1
                time.sleep(2)
                continue
        
        scope.close()
        print("✅ Disconnected from oscilloscope")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

def test_basic_communication():
    """Test basic communication with the oscilloscope"""
    
    siglent_address = "USB0::62700::60984::SDSMMFCD5R1059::0::INSTR"
    
    try:
        warnings.filterwarnings("ignore", category=UserWarning, module="pyvisa_py")
        
        rm = pyvisa.ResourceManager()
        scope = rm.open_resource(siglent_address)
        scope.timeout = 10000
        
        print("🔗 Testing basic communication...")
        
        # Test basic queries
        test_commands = [
            ('*IDN?', 'Device identification'),
            ('CHDR OFF', 'Turn off headers'),
            ('C1:VDIV?', 'Get voltage scale'),
            ('TDIV?', 'Get time scale'),
            ('TRMD?', 'Get trigger mode')
        ]
        
        for command, description in test_commands:
            try:
                if '?' in command:
                    response = scope.query(command)
                    print(f"✅ {description}: {repr(response)}")
                else:
                    scope.write(command)
                    print(f"✅ {description}: Command sent")
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ {description}: {e}")
        
        scope.close()
        
    except Exception as e:
        print(f"❌ Communication test failed: {e}")

if __name__ == "__main__":
    print("🔍 Siglent Oscilloscope Voltage Sampling")
    print("=" * 50)
    
    choice = input("Choose mode:\n1. Test basic communication\n2. Robust voltage sampling\nEnter choice (1 or 2): ")
    
    if choice == "1":
        test_basic_communication()
    elif choice == "2":
        sample_voltage_robust()
    else:
        print("Invalid choice. Running communication test...")
        test_basic_communication()
