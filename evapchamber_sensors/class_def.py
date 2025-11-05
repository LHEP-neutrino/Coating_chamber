import serial

# Code translations constants
MEASUREMENT_STATUS = {
    0: 'Measurement data okay',
    1: 'Underrange',
    2: 'Overrange',
    3: 'Sensor error',
    4: 'Sensor off (IKR, PKR, IMR, PBR)',
    5: 'No sensor (output: 5,2.0000E-2 [hPa])',
    6: 'Identification error'
}
GAUGE_IDS = {
    'TPR': 'Pirani Gauge or Pirani Capacitive gauge',
    'IKR9': 'Cold Cathode Gauge 10E-9 ',
    'IKR11': 'Cold Cathode Gauge 10E-11 ',
    'PKR': 'FullRange CC Gauge',
    'PBR': 'FullRange BA Gauge',
    'IMR': 'Pirani / High Pressure Gauge',
    'CMR': 'Linear gauge',
    'noSEn': 'no SEnsor',
    'noid': 'no identifier'
}
PRESSURE_UNITS = {0: 'mbar/bar', 1: 'Torr', 2: 'Pascal', 3: 'Micron', 4: 'hPascal', 5: 'Volt'}

class TPG36x(object):
    """Abstract class that implements the common driver for the TPG 361 and
    TPG 362 dual channel measurement and control unit. The driver implements
    the following 5 commands from the specification:

    * PNR: Program number (firmware version)
    * PR[1,2]: Pressure measurement (measurement data) gauge [1, 2]
    * PRX: Pressure measurement (measurement data) gauge 1 and 2
    * TID: Transmitter identification (gauge identification)
    * UNI: Pressure unit

    This class also contains the following class variables, for the specific
    characters that are used in the communication:

    :var ETX: End text (Ctrl-c), chr(3), \\x03
    :var CR: Carriage return, chr(13), \\r
    :var LF: Line feed, chr(10), \\n
    :var ENQ: Enquiry, chr(5), \\x05
    :var ACK: Acknowledge, chr(6), \\x06
    :var NAK: Negative acknowledge, chr(21), \\x15
    """

    ETX = chr(3)  # \x03
    CR  = chr(13)
    LF  = chr(10)
    ENQ = chr(5)  # \x05
    ACK = chr(6)  # \x06
    NAK = chr(21) # \x15

    def __init__(self, port='067B:2303', baudrate=9600): #/dev/ttyUSB0
        """Initialize internal variables and serial connection
        :param port: The COM port to open. See the documentation for
        `pyserial <http://pyserial.sourceforge.net/>`_ for an explanation
         of the possible value. The default value is '/dev/ttyUSB0'.
        :type port: str or int
        :param baudrate: 9600, 19200, 38400 where 9600 is the default
        :type baudrate: int
        """
        # The serial connection should be setup with the following parameters:
        # 1 start bit, 8 data bits, No parity bit, 1 stop bit, no hardware
        # handshake. These are all default for Serial and therefore not input
        # below
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=1)

    def _cr_lf(self, string):
        """Pad carriage return and line feed to a string
        :param string: String to pad
        :type string: str
        :returns: the padded string
        :rtype: str
        """
        return string + self.CR + self.LF

    def _send_command(self, command):
        """Send a command and check if it is positively acknowledged
        :param command: The command to send
        :type command: str
        :raises IOError: if the negative acknowledged or a unknown response is returned
        """
        self.serial.write((self._cr_lf(command)).encode()) #
        response = self.serial.readline()
        if response == self._cr_lf(self.NAK):
            message = 'Serial communication returned negative acknowledge'
            raise IOError(message)
        elif response != self._cr_lf(self.ACK):
            message = 'Serial communication returned unknown response:\n{}'\
                ''.format(repr(response))
            raise IOError(message)

    def _get_data(self):
        """Get the data that is ready on the device
        :returns: the raw data
        :rtype:str
        """
        self.serial.write(self.ENQ)
        data = self.serial.readline()
        return data.rstrip(self.LF).rstrip(self.CR)

    def _clear_output_buffer(self):
        """Clear the output buffer"""
        time.sleep(0.1)
        just_read = 'start value'
        out = ''
        while just_read != '':
            just_read = self.serial.read()
            out += just_read
        return out

    def pressure_unit(self):
        """Return the pressure unit
        :return: the pressure unit
        :rtype: str
        """
        self._send_command('UNI')
        unit_code = int(self._get_data())
        return PRESSURE_UNITS[unit_code]

class TPG362(TPG36x):
    """Driver for the TPG 362 dual channel measurement and control unit"""

    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        """Initialize internal variables and serial connection
        :param port: The COM port to open. See the documentation for
        `pyserial <http://pyserial.sourceforge.net/>`_ for an explanation
         of the possible value. The default value is '/dev/ttyUSB0'.
        :type port: str or int
        :param baudrate: 9600, 19200, 38400 where 9600 is the default
        :type baudrate: int
        """
        super(TPG362, self).__init__(port=port, baudrate=baudrate)
