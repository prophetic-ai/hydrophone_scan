"""
Hardware control for Hydrophone Scanner
Handles Arduino and Oscilloscope communication.
"""

class HardwareController:
    def __init__(self, arduino_port, scope_address):
        """Initialize hardware connections"""
        self.arduino_port = arduino_port
        self.scope_address = scope_address
        self._setup_connections()

    def _setup_connections(self):
        """Establish hardware connections"""
        # Setup Arduino
        # Setup Oscilloscope

    def move_axis(self, axis, steps):
        """
        Move specified axis by number of steps
        axis: 'x', 'y', or 'z'
        steps: number of steps (positive or negative)
        """

    def get_measurement(self):
        """
        Get single measurement from oscilloscope
        Returns: peak positive, peak negative
        """

    def return_to_start(self):
        """Return to scan start position"""