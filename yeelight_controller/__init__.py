from __future__ import annotations
import socket
import struct
import json
import logging
import time

MULTICAST_IP = '239.255.255.250'
MULTICAST_PORT = 1982
SEARCH_MESSAGE = '''M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1982\r\n
MAN: "ssdp:discover"\r\n
ST: wifi_bulb\r\n'''
READ_DELAY = 1

CONTROL_PORT = 55443

# default logging
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(levelname)s - [%(name)s] - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
DEFAULT_LOGGER = logging.getLogger("YEELIGHT CONTROLLER")


class LightBulb:
    """Yeelight lightbulb handler."""
    current_message_id = 0

    def __init__(self, ip_address, device_id=None, power=None, brightness=None, color_mode=None,
                 color_temperature=None, rgb=None, hue=None, saturation=None, name=None,
                 fw_ver=None, log=None):
        self.device_id = device_id
        self.log = DEFAULT_LOGGER
        if log is not None:
            self.log = log
        self.on_notify = None
        self.on_error = None
        self.power = power
        self.brightness = brightness
        self.color_mode = color_mode
        self.color_temperature = color_temperature
        self.rgb = rgb
        self.hue = hue
        self.saturation = saturation
        self.name = name
        self.fw_ver = fw_ver
        self.ip_address = ip_address
        self.port = CONTROL_PORT
        self.__sock = None
        self.effect = 'smooth'
        self.duration = 500
        self.connect()


    def __repr__(self):
        return 'ID: {} at {}'.format(self.device_id, self.ip_address)


    def connect(self):
        """Connects to light bulb."""
        if self.__sock is None:
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.settimeout(5)
            try:
                self.__sock.connect((self.ip_address, self.port))
                self.log.debug('CONNECTED')
                # TODO get props
            except socket.timeout:
                self.log.error("COULD NOT CONNECT", exc_info=True)


    def turn_on(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['on', self.effect, self.duration]
        )
        self.__send_message(msg)


    def turn_off(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['off', self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_brightness(self, brightness: int):
        """Sets the brightness.

        Arguments:
            brightness {int} -- Brightness in percentage.
        """
        msg = self.__create_message(
            'set_bright',
            [brightness, self.effect, self.duration]
        )
        self.__send_message(msg)


    def toggle(self):
        """Toggles the device's state."""
        msg = self.__create_message(
            'toggle',
            []
        )
        self.__send_message(msg)


    def set_temperature(self, color_temp: int):
        """Sets the color temperature of the device.

        Arguments:
            color_temp {int} -- Color temperature. Range: 1700 - 6500.
        """
        msg = self.__create_message(
            'set_ct_abx',
            [color_temp, self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_rgb(self, red: int, green: int, blue: int):
        """Sets the color in RGB values.

        Arguments:
            red {int} -- Red intensity. Range: 0-255
            green {int} -- Green intensity. Range: 0-255
            blue {int} -- Blue intensity. Range: 0-255
        """
        color = red * 65536 + green * 256 + blue
        msg = self.__create_message(
            'set_rgb',
            [color, self.effect, self.duration]
        )
        self.__send_message(msg)


    def set_hsv(self, hue: int, sat: int):
        """Sets the color in HSV.

        Arguments:
            hue {int} -- Range: 0 - 359
            sat {int} -- Range: 0 - 100 (%)
        """
        msg = self.__create_message(
            'set_hsv',
            [hue, sat, self.effect, self.duration]
        )
        self.__send_message(msg)


    def __send_message(self, msg: bytes):
        """Sends message to device.

        Arguments:
            msg {bytes} -- Message encoded in bytes.
        """
        self.log.debug('SENDING MESSAGE: %s', msg.decode().strip())
        self.__sock.send(msg)
        try:
            data, _ = self.__sock.recvfrom(4048)
            # handling multiple json formatted messages
            messages = data.decode().split('\r\n')
            for message in messages:
                if message:
                    message_json = json.loads(message)
                    if 'error' in message_json:
                        self.log.error('ERROR RECEIVED %s', message_json)
                        if self.on_error:
                            self.on_error(message_json) # pylint: disable=not-callable
                    elif 'method' in message_json:
                        self.log.debug('NOTIFY MESSAGE RECEIVED: %s', message_json)
                        self.___process_notification_message(message_json)
                        if self.on_notify:
                            self.on_notify(message_json) # pylint: disable=not-callable
        except socket.timeout:
            pass


    def ___process_notification_message(self, message: dict):
        """Stores received prop values in notification message.

        Arguments:
            message {dict}
        """
        params = message['params']
        for prop, value in params.items():
            if prop == 'power':
                self.power = value
            elif prop == 'bright':
                self.brightness = value
            elif prop == 'color_mode':
                self.color_mode = int(value)
            elif prop == 'ct':
                self.color_temperature = int(value)
            elif prop == 'rbg':
                self.rgb = int(value)
            elif prop == 'hue':
                self.hue = int(value)
            elif prop == 'sat':
                self.saturation = int(value)


    @staticmethod
    def __create_message(method_name: str, params: list) -> bytes:
        """Creates message for device.

        Arguments:
            method_name {str}
            params {list}

        Returns:
            bytes -- Encoded message.
        """
        LightBulb.current_message_id += 1
        msg = {
            'id': LightBulb.current_message_id,
            'method': method_name,
            'params': params
        }
        return (json.dumps(msg) + '\r\n').encode()


    @staticmethod
    def parse_search_response(message: bytes) -> dict:
        """Parses response to discovery multicast message.
           Extracts headers from response message.

        Arguments:
            message {bytes} -- Response message.

        Returns:
            dict -- Dictionary containing headers.
        """
        decoded = message.decode()
        rows = decoded.split('\r\n')
        headers = dict()
        if rows[0] == 'HTTP/1.1 200 OK':
            for row in rows:
                splitted = row.split(': ')
                if len(splitted) == 2:
                    header_name = splitted[0].lower()
                    header_value = splitted[1]
                    headers[header_name] = header_value
        return headers


    @staticmethod
    def discover(host_ip: str, search_timeout: int=20) -> LightBulb:
        """Discovers one device on network.

        Arguments:
            host_ip {str} -- Ip address of host machine.

        Keyword Arguments:
            search_timeout {int} -- Search timeout in seconds. (default: {20})

        Returns:
            LightBulb -- LightBulb object.
        """
        discovered = False
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host_ip, MULTICAST_PORT))
        sock.settimeout(3)
        ttl = struct.pack('b', 5)
        started_searching = time.time()
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        try:
            while not discovered:
                DEFAULT_LOGGER.debug('Sending multicast message')
                sock.sendto(SEARCH_MESSAGE.encode(), (MULTICAST_IP, MULTICAST_PORT))
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    DEFAULT_LOGGER.debug('SOCKET TIMEOUT')
                    if time.time() - started_searching >= search_timeout:
                        DEFAULT_LOGGER.error("COULD NOT FIND DEVICE")
                        return None
                else:
                    discovered = True
                    parsed_msg = LightBulb.parse_search_response(data)

                    ip = parsed_msg["location"].split("//")[1].split(':')[0]

                    new_device = LightBulb(
                        device_id=parsed_msg['id'],
                        ip_address=ip,
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
