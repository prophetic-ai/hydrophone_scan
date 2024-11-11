"""
Core scanning logic
Handles scan patterns and data acquisition.
"""

class ScanController:
    def __init__(self, hardware):
        self.hardware = hardware
        self.data = []
        self.start_position = None

    def run_scan(self, scan_type, dimensions):
        """
        Execute scan pattern and collect data
        scan_type: '1d_x', '1d_y', '1d_z', '2d_xy', '2d_xz', '2d_yz'
        dimensions: dict with scan dimensions
        """
        self._record_start_position()
        
        if scan_type.startswith('1d'):
            self._run_1d_scan(dimensions)
        else:
            self._run_2d_scan(dimensions)
            
        self.hardware.return_to_start()
        return self.data

    def _run_1d_scan(self, dimensions):
        """Execute 1D scan pattern"""

    def _run_2d_scan(self, dimensions):
        """Execute 2D scan pattern """