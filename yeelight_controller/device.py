"""Yeelight controller module"""
from __future__ import annotations
import socket
import struct
import json
import logging
import time
from .enums import Effect

MULTICAST_IP = '239.255.255.250'
MULTICAST_PORT = 1982
SEARCH_MESSAGE = '''M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1982\r\n
MAN: "ssdp:discover"\r\n
ST: wifi_bulb\r\n'''

CONTROL_PORT = 55443
SOCKET_TIMEOUT = 5

# default logging
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(levelname)s - [%(name)s] - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
DEFAULT_LOGGER = logging.getLogger("YEELIGHT CONTROLLER")


class LightBulb:
    """Yeelight lightbulb handler."""
    current_message_id = 0

    def __init__(self, ip_address, device_id=None, name=None, fw_ver=None, log=None, effect:Effect=Effect.smooth, duration=500):
        # logging
        self.__log = DEFAULT_LOGGER
        if log is not None:
            self.__log = log

        # callbacks
        self.on_notify = None 
        self.on_error = None

        #props
        self.__device_id = device_id
        self.__power = None
        self.__brightness = None
        self.__color_mode = None
        self.__color_temperature = None
        self.__rgb = None
        self.__hue = None
        self.__saturation = None
        self.__name = None
        self.__fw_ver = None

        # networking
        self.__ip_address = ip_address
        self.__sock = None

        #transition
        self.__effect = effect.name
        self.__duration = duration

        self.connect()


    def __repr__(self):
        return 'Yeelight RGB LightBulb ID: {} ip address {}'.format(self.__device_id, self.__ip_address)


    def connect(self):
        """Connects to light bulb."""
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.settimeout(SOCKET_TIMEOUT)
        try:
            self.__sock.connect((self.__ip_address, CONTROL_PORT))
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
        result = self.__send_message(msg)
        if result:
            props = result['result']
            self.__power = props[0]
            self.__brightness = int(props[1])
            self.__color_temperature = int(props[2])
            self.__color_mode = int(props[3])
            self.__rgb = int(props[4])
            self.__hue = int(props[5])
            self.__saturation = int(props[6])


    def turn_on(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['on', self.__effect, self.__duration]
        )
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__power = 'on'


    def turn_off(self):
        """Turns on the lightbulb."""
        msg = self.__create_message(
            'set_power',
            ['off', self.__effect, self.__duration]
        )
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__power = 'off'


    def set_brightness(self, brightness: int):
        """Sets the brightness.

        Arguments:
            brightness {int} -- Brightness in percentage.
        """
        msg = self.__create_message(
            'set_bright',
            [brightness, self.__effect, self.__duration]
        )
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__brightness = brightness


    def toggle(self):
        """Toggles the device's state."""
        msg = self.__create_message(
            'toggle',
            []
        )
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            if self.__power == 'on':
                self.__power = 'off'
            else:
                self.__power = 'on'


    def set_temperature(self, color_temp: int):
        """Sets the color temperature of the device.

        Arguments:
            color_temp {int} -- Color temperature. Range: 1700 - 6500.
        """
        msg = self.__create_message(
            'set_ct_abx',
            [color_temp, self.__effect, self.__duration]
        )
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__color_temperature = color_temp


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
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__rgb = color


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
        result = self.__send_message(msg)
        if result and result['result'][0] == 'ok':
            self.__hue = hue
            self.__saturation = sat


    def __send_message(self, msg: dict) -> dict:
        """Sends command message.

        Args:
            msg (dict): Message dictionary.

        Returns:
            dict: Response description.
        """
        self.__log.debug('SENDING MESSAGE: %s', msg)
        self.__sock.send((json.dumps(msg) + '\r\n').encode())
        result_message = None
        while result_message is None:
            try:
                data, _ = self.__sock.recvfrom(16 * 1024)
                # handling multiple json formatted messages
                messages = data.decode().split('\r\n')
                for message in messages:
                    if message:
                        message_json = json.loads(message)
                        if 'error' in message_json:
                            self.__log.error('ERROR RECEIVED %s', message_json)
                            if self.on_error:
                                self.on_error(message_json) # pylint: disable=not-callable
                            return
                        elif 'method' in message_json:
                            self.__log.debug('NOTIFY MESSAGE RECEIVED: %s', message_json)
                            self.__process_notification_message(message_json)
                            if self.on_notify:
                                self.on_notify(message_json) # pylint: disable=not-callable
                        elif 'result' in message_json:
                            if message_json['id'] == msg['id']:
                                result_message = message_json
            except socket.timeout:
                self.__log.warn('SOCKET TIMEOUT')
                return None
            except socket.error as ex:
                self.__log.error(ex)
                self.__log.debug('TRYING TO RECONNECT')
                self.connect()
                return None
        return result_message


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
                self.__brightness = int(value)
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
    def __create_message(method_name: str, params: list) -> dict:
        """Creates command message.

        Args:
            method_name (str): Method name.
            params (list): List of method parameters.

        Returns:
            dict: Message dictionary.
        """
        LightBulb.current_message_id += 1
        msg = {
            'id': LightBulb.current_message_id,
            'method': method_name,
            'params': params
        }
        return msg


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
                        ip_address=ip
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
