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
        # logging
        self.__log = DEFAULT_LOGGER
        if log is not None:
            self.__log = log

        # callbacks
        self.on_notify = None
        self.on_error = None

        #props
        self.__device_id = device_id
        self.__power = power
        self.__brightness = brightness
        self.__color_mode = color_mode
        self.__color_temperature = color_temperature
        self.__rgb = rgb
        self.__hue = hue
        self.__saturation = saturation
        self.__name = name
        self.__fw_ver = fw_ver

        # networking
        self.__ip_address = ip_address
        self.__port = CONTROL_PORT
        self.__sock = None

        #transition
        self.__effect = 'smooth'
        self.__duration = 500

        self.connect()


    def __repr__(self):
        return 'ID: {} at {}'.format(self.__device_id, self.__ip_address)


    def connect(self):
        """Connects to light bulb."""
        if self.__sock is None:
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.settimeout(5)
            try:
                self.__sock.connect((self.__ip_address, self.__port))
                self.__log.debug('CONNECTED')
                self.__get_props()
            except socket.timeout:
                self.__log.error("COULD NOT CONNECT", exc_info=True)


    def __get_props(self):
        """Reads property values from device."""
        msg = self.__create_message(
            'get_prop',
            ['power', 'bright', 'ct', 'color_mode', 'rgb', 'hue', 'sat']
        )
        self.__send_message(msg)


    def turn_on(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['on', self.__effect, self.__duration]
        )
        self.__send_message(msg)


    def turn_off(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['off', self.__effect, self.__duration]
        )
        self.__send_message(msg)


    def set_brightness(self, brightness: int):
        """Sets the brightness.

        Arguments:
            brightness {int} -- Brightness in percentage.
        """
        msg = self.__create_message(
            'set_bright',
            [brightness, self.__effect, self.__duration]
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
            [color_temp, self.__effect, self.__duration]
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
            [color, self.__effect, self.__duration]
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
            [hue, sat, self.__effect, self.__duration]
        )
        self.__send_message(msg)


    def __send_message(self, msg: bytes):
        """Sends message to device.

        Arguments:
            msg {bytes} -- Message encoded in bytes.
        """
        self.__log.debug('SENDING MESSAGE: %s', msg.decode().strip())
        self.__sock.send(msg)
        try:
            data, _ = self.__sock.recvfrom(4048)
            # handling multiple json formatted messages
            messages = data.decode().split('\r\n')
            for message in messages:
                if message:
                    message_json = json.loads(message)
                    if 'error' in message_json:
                        self.__log.error('ERROR RECEIVED %s', message_json)
                        if self.on_error:
                            self.on_error(message_json) # pylint: disable=not-callable
                    elif 'method' in message_json:
                        self.__log.debug('NOTIFY MESSAGE RECEIVED: %s', message_json)
                        self.__process_notification_message(message_json)
                        if self.on_notify:
                            self.on_notify(message_json) # pylint: disable=not-callable
                    elif 'result' in message_json and message_json['id'] == 1:
                        # only processing first message result which is always 'get_prop'
                        self.__save_props(message_json)
        except socket.timeout:
            pass

    def __save_props(self, message: dict):
        """Stores received prop values in result message.

        Arguments:
            message {dict}
        """
        result = message['result']
        self.__power = result[0]
        self.__brightness = result[1]
        self.__color_temperature = result[2]
        self.__color_mode = result[3]
        self.__rgb = result[4]
        self.__hue = result[5]
        self.__saturation = result[6]


    def __process_notification_message(self, message: dict):
        """Stores received prop values in notification message.

        Arguments:
            message {dict}
        """
        params = message['params']
        for prop, value in params.items():
            if prop == 'power':
                self.__power = value
            elif prop == 'bright':
                self.__brightness = value
            elif prop == 'color_mode':
                self.__color_mode = int(value)
            elif prop == 'ct':
                self.__color_temperature = int(value)
            elif prop == 'rbg':
                self.__rgb = int(value)
            elif prop == 'hue':
                self.__hue = int(value)
            elif prop == 'sat':
                self.__saturation = int(value)


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


    @property
    def device_id(self):
        return self.__device_id

    
    @property
    def power(self):
        return self.__power

    
    @property
    def brightness(self):
        return self.__brightness

    
    @property
    def color_mode(self):
        return self.__color_mode


    @property
    def color_temperature(self):
        return self.__color_temperature


    @property
    def rgb(self):
        return self.__rgb


    @property
    def hue(self):
        return self.__hue


    @property
    def saturation(self):
        return self.__saturation


    @property
    def name(self):
        return self.__name


    @property
    def fw_ver(self):
        return self.__fw_ver


    @property
    def ip_address(self):
        return self.__ip_address


    @property
    def port(self):
        return self.__port
