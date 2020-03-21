import socket
import struct
import json
import logging

MULTICAST_IP = '239.255.255.250'
PORT = 1982
SEARCH_MESSAGE = '''M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1982\r\n
MAN: "ssdp:discover"\r\n
ST: wifi_bulb\r\n'''

# default logging
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(levelname)s - [%(name)s] - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
DEFAULT_LOGGER = logging.getLogger("YEELIGHT CONTROLLER")


class LightBulb:
    current_message_id = 0

    def __init__(self, location, device_id=None, power=None, brightness=None, color_mode=None,
                 color_temperature=None, rgb=None, hue=None, saturation=None, name=None,
                 fw_ver=None, log=None):
        self.device_id = device_id
        self.log = DEFAULT_LOGGER
        if log is not None:
            self.log = log
        self.location = location
        self.power = power
        self.brightness = brightness
        self.color_mode = color_mode
        self.color_temperature = color_temperature
        self.rgb = rgb
        self.hue = hue
        self.saturation = saturation
        self.name = name
        self.fw_ver = fw_ver
        loc = location.split('//')[1]
        self.ip_address = loc.split(':')[0]
        self.port = int(loc.split(':')[1])
        self.__sock = None
        self.effect = 'smooth'
        self.duration = 500
        self.connect()
        self.__host_address = '0.0.0.0'


    def __repr__(self):
        return 'ID: {} at {}'.format(self.device_id, self.location)


    def connect(self):
        """Connects to light bulb."""
        if self.__sock is None:
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.settimeout(3)
            try:
                self.__sock.connect((self.ip_address, self.port))
                self.log.debug('CONNECTED')
            except socket.timeout:
                self.log.error("COULD NOT CONNECT", exc_info=True)


    def turn_on(self):
        """Turns on the light bulb."""
        msg = self.__create_message(
            'set_power',
            ['on', self.effect, self.duration]
        )
        self.__send_message(msg)


    def turn_off(self):
        """Turns on the light bulb."""
        msg = self.__create_message(
            'set_power',
            ['off', self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_brightness(self, brigthness):
        """Sets the brightness."""
        msg = self.__create_message(
            'set_bright',
            [brigthness, self.effect, self.duration]
        )
        self.__send_message(msg)


    def toggle(self):
        """Toggles the device's state."""
        msg = self.__create_message(
            'toggle',
            []
        )
        self.__send_message(msg)


    def set_temperature(self, color_temp):
        """Sets the color temperature of the device."""
        msg = self.__create_message(
            'set_ct_abx',
            [color_temp, self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_rgb(self, r, g, b):
        """Sets RGB values."""
        color = r * 65536 + g * 256 + b
        msg = self.__create_message(
            'set_rgb',
            [color, self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_hsv(self, hue, sat):
        """Sets hsv."""
        msg = self.__create_message(
            'set_hsv',
            [hue, sat, self.effect, self.duration]
        )
        self.__send_message(msg)


    def __send_message(self, msg):
        """Sends message to the device."""
        try:
            self.log.debug('SENDING MESSAGE: %s', msg.decode().strip())
            self.__sock.send(msg)
            data, _ = self.__sock.recvfrom(1024)
            # handling multiple json formatted messages
            messages = data.decode().split('\r\n')
            for message in messages:
                if message:
                    self.__process_response(message)
        except socket.timeout:
            self.log.debug("TIMEOUT")


    def __create_message(self, method_name, params):
        """Creates message for the device."""
        LightBulb.current_message_id += 1
        msg = {
            'id': LightBulb.current_message_id,
            'method': method_name,
            'params': params
        }
        return (json.dumps(msg) + '\r\n').encode()


    @staticmethod
    def parse_search_response(message):
        """Parses response to discovery multicast message."""
        if isinstance(message, bytes):
            message = message.decode()
        rows = message.split('\r\n')
        headers = dict()
        if rows[0] == 'HTTP/1.1 200 OK':
            for row in rows:
                s = row.split(': ')
                if len(s) == 2:
                    header_name = s[0].lower()
                    header_value = s[1]
                    headers[header_name] = header_value
        return headers


    def __process_response(self, message: str):
        """Parsers response mesage."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            self.log.error("Unexpected response message: %s", message)
            return
        # only processing responses containing property values
        if 'method' in data and data['method'] == 'props':
            self.log.debug('RESPONSE: %s', data)
            for param in data['params']:
                value = data['params'][param]
                if param == 'rgb':
                    self.rgb = value
                elif param == 'hue':
                    self.hue = value
                elif param == 'power':
                    self.power = value
                elif param == 'bright':
                    self.brightness = value
                elif param == 'ct':
                    self.color_temperature = value
                elif param == 'color_mode':
                    self.color_mode = value
                elif param == 'hue':
                    self.hue = value
                elif param == 'sat':
                    self.saturation = value
        elif 'error' in data:
            self.log.warning("Error response received: %s", data)


    @staticmethod
    def discover(host_ip='0.0.0.0'):
        """Discovers a LightBulb on the network."""
        #hostname = socket.gethostname()
        discovered = False
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host_ip, PORT))
        sock.settimeout(3)
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        try:
            while not discovered:
                DEFAULT_LOGGER.debug('Sending multicast message')
                sock.sendto(SEARCH_MESSAGE.encode(), (MULTICAST_IP, PORT))
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    DEFAULT_LOGGER.debug('TIMEOUT')
                else:
                    discovered = True
                    parsed_msg = LightBulb.parse_search_response(data)
                    new_device = LightBulb(
                        device_id=parsed_msg['id'],
                        location=parsed_msg['location'],
                        power=parsed_msg['power'],
                        brightness=parsed_msg['bright'],
                        color_mode=parsed_msg['color_mode'],
                        color_temperature=parsed_msg['ct'],
                        rgb=parsed_msg['rgb'],
                        hue=parsed_msg['hue'],
                        saturation=parsed_msg['sat']
                    )
                    return new_device
        finally:
            sock.close()
