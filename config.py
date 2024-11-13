"""
YAML configuration loader with validation for Hydrophone Scanner
"""

import yaml
import os
import logging
from typing import Dict

def validate_config(config: Dict) -> None:
    """Validate configuration values and scan dimensions"""
    
    scan_type = config['scan']['type']
    dims = config['scan']['dimensions']
    
    # Check calibration value is positive
    if config['scan']['calibration_value'] <= 0:
        raise ValueError("Calibration value must be positive")
        
    # Check resolution is positive
    if dims['resolution'] <= 0:
        raise ValueError("Resolution must be positive")
        
    # Check base path exists or create it
    base_path = config['scan']['base_path']
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        logging.info(f"Created base path directory: {base_path}")
        
    # Validate scan dimensions based on scan type
    if scan_type.startswith('1d'):
        # For 1D scans, verify only one dimension is non-zero
        axis = scan_type[-1]  # x, y, or z
        active_dims = [k for k in ['x', 'y', 'z'] if dims[k] != 0]
        
        if len(active_dims) != 1:
            raise ValueError("1D scan should have exactly one non-zero dimension")
            
        if active_dims[0] != axis:
            raise ValueError(f"1D scan along {axis} axis has wrong dimension set")
            
    elif scan_type.startswith('2d'):
        # For 2D scans, verify exactly two dimensions are non-zero
        axes = scan_type[-2:]  # xy, xz, or yz
        active_dims = [k for k in ['x', 'y', 'z'] if dims[k] != 0]
        
        if len(active_dims) != 2:
            raise ValueError("2D scan should have exactly two non-zero dimensions")
            
        if not all(axis in axes for axis in active_dims):
            raise ValueError(f"2D scan in {axes} plane has wrong dimensions set")
    
def load_config(config_path: str = "config.yaml") -> Dict:
    """Load and validate configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        validate_config(config)
        return config
        
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        raise

