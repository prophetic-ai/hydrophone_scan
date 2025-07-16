"""
Oscilloscope Reader for Hydrophone Scanner
Handles Siglent oscilloscope communication and voltage measurements.
"""

import time
import warnings
import numpy as np
import pyvisa
from typing import Dict, Optional, Any


class OscilloscopeReader:
    
    def __init__(self, scope_address: str, timeout: int = 15000):
        self.scope_address = scope_address
        self.scope: Optional[Any] = None  # Using Any to avoid pyvisa type issues
        self.scope_settings: Dict[str, Optional[str]] = {}
        self.consecutive_errors = 0
        self.timeout = timeout
        
        if scope_address:
            self._connect()
    
    def _connect(self) -> bool:
        """Connect to oscilloscope using robust connection methods"""
        if not self.scope_address:
            print("⚠️  No oscilloscope address provided - voltage sampling disabled")
            return False
        
        try:
            print("\n🔗 Connecting to Siglent oscilloscope...")
            
            # Suppress USB firmware warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="pyvisa_py")
            
            rm = pyvisa.ResourceManager()
            self.scope = rm.open_resource(self.scope_address)
            self.scope.timeout = self.timeout
            
            # More robust connection with retries
            connected = False
            for attempt in range(3):
                try:
                    self.scope.write('CHDR OFF')
                    time.sleep(0.5)
                    
                    # Test basic communication
                    idn = self.scope.query('*IDN?')
                    print(f"✅ Oscilloscope connected: {idn.strip()}")
                    connected = True
                    break
                    
                except Exception as e:
                    print(f"Connection attempt {attempt + 1} failed: {e}")
                    time.sleep(1)
            
            if not connected:
                print("❌ Could not establish stable oscilloscope connection")
                self.scope = None
                return False
            
            # Read current settings
            self._read_settings()
            return True
            
        except Exception as e:
            print(f"❌ Oscilloscope connection error: {e}")
            self.scope = None
            return False

    def _read_settings(self) -> None:
        """Read and store current oscilloscope settings"""
        if not self.scope:
            return
            
        print("📋 Reading oscilloscope settings...")
        
        setting_queries = {
            'vdiv': 'C1:VDIV?',
            'tdiv': 'TDIV?',
            'coupling': 'C1:CPL?',
            'trigger_mode': 'TRMD?',
            'offset': 'C1:OFST?'
        }
        
        for setting, query in setting_queries.items():
            try:
                response = self.scope.query(query)
                self.scope_settings[setting] = response.strip()
                print(f"  {setting}: {response.strip()}")
            except Exception as e:
                print(f"  ⚠️  Could not read {setting}: {e}")
                self.scope_settings[setting] = None

    def is_connected(self) -> bool:
        """Check if oscilloscope is connected"""
        return self.scope is not None

    def get_settings(self) -> Dict[str, Optional[str]]:
        """Get current oscilloscope settings"""
        return self.scope_settings.copy()

    def sample_voltage_detailed(self) -> Optional[Dict[str, Any]]:
        """Sample voltage with detailed breakdown: positive peak, negative peak, and peak-to-peak"""
        if not self.scope:
            print("❌ Oscilloscope not connected")
            return None
        
        try:
            # Method 1: Try to get individual peak measurements
            pos_peak = None
            neg_peak = None
            vpp = None
            method_used = None
            
            # Try to get positive peak
            pos_peak_methods = [
                ('PAVA_MAX', 'C1:PAVA? MAX'),
                ('MEAS_VMAX', 'MEAS:VMAX? C1'),
                ('PARA_MAX', 'PARA? C1,MAX')
            ]
            
            for method_name, command in pos_peak_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        pos_peak = float(value_str.rstrip('V'))
                        method_used = method_name
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        pos_peak = float(response.strip())
                        method_used = method_name
                        break
                except Exception:
                    continue
            
            # Try to get negative peak
            neg_peak_methods = [
                ('PAVA_MIN', 'C1:PAVA? MIN'),
                ('MEAS_VMIN', 'MEAS:VMIN? C1'),
                ('PARA_MIN', 'PARA? C1,MIN')
            ]
            
            for method_name, command in neg_peak_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        neg_peak = float(value_str.rstrip('V'))
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        neg_peak = float(response.strip())
                        break
                except Exception:
                    continue
            
            # Try to get peak-to-peak
            vpp_methods = [
                ('PAVA_PKPK', 'C1:PAVA? PKPK'),
                ('MEAS_VAMP', 'MEAS:VAMP? C1'),
                ('PARA_PKPK', 'PARA? C1,PKPK')
            ]
            
            for method_name, command in vpp_methods:
                try:
                    response = self.scope.query(command)
                    if ',' in response:
                        value_str = response.split(',')[1].strip()
                        vpp = float(value_str.rstrip('V'))
                        if not method_used:
                            method_used = method_name
                        break
                    elif response.replace('.', '').replace('-', '').replace('+', '').replace('e', '').replace('E', '').isdigit():
                        vpp = float(response.strip())
                        if not method_used:
                            method_used = method_name
                        break
                except Exception:
                    continue
            
            # If individual peaks failed, try waveform method
            if pos_peak is None or neg_peak is None:
                try:
                    self.scope.write('C1:WF? DAT1')
                    time.sleep(0.5)
                    
                    raw_data = self.scope.read_raw()
                    
                    if len(raw_data) > 10:
                        # Try to parse waveform data
                        data = None
                        try:
                            if b'#9' in raw_data:
                                header_end = raw_data.find(b'#9') + 11
                                data_bytes = raw_data[header_end:-1]
                                data = np.frombuffer(data_bytes, dtype=np.int8)
                            elif len(raw_data) > 16:
                                data_bytes = raw_data[16:-1]
                                data = np.frombuffer(data_bytes, dtype=np.int8)
                        except:
                            pass
                        
                        if data is not None and len(data) > 0:
                            # Get current scaling
                            vdiv_val = 1.0
                            offset_val = 0.0
                            
                            vdiv_setting = self.scope_settings.get('vdiv')
                            if vdiv_setting:
                                try:
                                    vdiv_val = float(vdiv_setting.split()[-1].strip('V'))
                                except:
                                    pass
                            
                            offset_setting = self.scope_settings.get('offset')
                            if offset_setting:
                                try:
                                    offset_val = float(offset_setting.split()[-1].strip('V'))
                                except:
                                    pass
                            
                            # Convert to voltage
                            voltage_array = (data / 25.0) * vdiv_val + offset_val
                            
                            pos_peak = np.max(voltage_array)
                            neg_peak = np.min(voltage_array)
                            vpp = pos_peak - neg_peak
                            method_used = 'WAVEFORM'
                
                except Exception as e:
                    pass
            
            # Calculate missing values if we have some data
            if pos_peak is not None and neg_peak is not None and vpp is None:
                vpp = pos_peak - neg_peak
            elif vpp is not None and pos_peak is not None and neg_peak is None:
                neg_peak = pos_peak - vpp
            elif vpp is not None and neg_peak is not None and pos_peak is None:
                pos_peak = neg_peak + vpp
            
            if pos_peak is not None or neg_peak is not None or vpp is not None:
                self.consecutive_errors = 0
                return {
                    'positive_peak': pos_peak,
                    'negative_peak': neg_peak,
                    'peak_to_peak': vpp,
                    'method': method_used
                }
            
            # If all methods fail
            self.consecutive_errors += 1
            return None
            
        except Exception as e:
            self.consecutive_errors += 1
            print(f"❌ Voltage sampling error: {e}")
            return None

    def continuous_sampling(self) -> None:
        """Continuous voltage sampling mode with detailed breakdown"""
        if not self.scope:
            print("❌ Oscilloscope not connected - cannot sample voltage")
            return
        
        print("\n📊 Continuous Voltage Sampling")
        print("=" * 70)
        print("Press Ctrl+C to stop sampling")
        print("=" * 70)
        print(f"{'Sample':>6} {'Pos Peak':>10} {'Neg Peak':>10} {'Peak-Peak':>10} {'Method':>12}")
        print("-" * 70)
        
        sample_count = 0
        
        try:
            while True:
                voltage_data = self.sample_voltage_detailed()
                
                if voltage_data:
                    sample_count += 1
                    pos_peak = voltage_data['positive_peak']
                    neg_peak = voltage_data['negative_peak']
                    vpp = voltage_data['peak_to_peak']
                    method = voltage_data['method']
                    
                    # Format the output
                    pos_str = f"{pos_peak:+7.3f}V" if pos_peak is not None else "   N/A  "
                    neg_str = f"{neg_peak:+7.3f}V" if neg_peak is not None else "   N/A  "
                    vpp_str = f"{vpp:7.3f}V" if vpp is not None else "   N/A "
                    
                    print(f"{sample_count:6d} {pos_str:>10} {neg_str:>10} {vpp_str:>10} {method:>12}")
                    
                    self.consecutive_errors = 0
                else:
                    print(f"⚠️  No measurement available (error count: {self.consecutive_errors})")
                    
                    if self.consecutive_errors > 5:
                        print("Too many consecutive errors - trying to reconnect...")
                        self._connect()
                
                time.sleep(1)  # Slower sampling to reduce USB stress
                
        except KeyboardInterrupt:
            print("\n\n🛑 Sampling stopped by user")

    def reconnect(self) -> bool:
        """Attempt to reconnect to oscilloscope"""
        return self._connect()

    def close(self) -> None:
        """Close oscilloscope connection"""
        if self.scope:
            self.scope.close()
            print("Oscilloscope disconnected")
            self.scope = None 