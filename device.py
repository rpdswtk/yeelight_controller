import socket
import struct
import json

MULTICAST_IP = '239.255.255.250'
PORT = 1982
SEARCH_MESSAGE = '''M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1982\r\n
MAN: "ssdp:discover"\r\n
ST: wifi_bulb\r\n'''


class LightBulb:
    current_message_id = 0

    def __init__(self, id, location, power, brightness, color_mode,
                 color_temperature, rgb, hue, saturation, name=None,
                 fw_ver=None):
        self.id = id
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
        self.ip = loc.split(':')[0]
        self.port = int(loc.split(':')[1])
        self.__sock = None
        self.effect = 'smooth'
        self.duration = 500

    def __repr__(self):
        return 'ID: {} at {}'.format(self.id, self.location)

    def connect(self):
        if self.__sock is None:
            self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.connect((self.ip, self.port))
            self.__sock.settimeout(3)

    def turn_on(self):
        msg = self.__create_message(
            'set_power',
            ['on', self.effect, self.duration]
        )
        self.__send_message(msg)

    def turn_off(self):
        msg = self.__create_message(
            'set_power',
            ['off', self.effect, self.duration]
        )
        self.__send_message(msg)

    def set_brightness(self, brigthness):
        msg = self.__create_message(
            'set_bright',
            [brigthness, self.effect, self.duration]
        )
        self.__send_message(msg)

    def toggle(self):
        msg = self.__create_message(
            'toggle',
            []
        )
        self.__send_message(msg)

    def set_temperature(self, color_temp):
        msg = self.__create_message(
            'set_ct_abx',
            [color_temp, self.effect, self.duration]
        )
        self.__send_message(msg)

    def set_rgb(self, r, g, b):
        color = r * 65536 + g * 256 + b
        msg = self.__create_message(
            'set_rgb',
            [color, self.effect, self.duration]
        )
        self.__send_message(msg)

    def set_hsv(self, hue, sat):
        msg = self.__create_message(
            'set_hsv',
            [hue, sat, self.effect, self.duration]
        )
        self.__send_message(msg)

    def __send_message(self, msg):
        try:
            print('SENDING MESSAGE:')
            print(msg.decode())
            self.__sock.send(msg)
            data, server = self.__sock.recvfrom(100)
            print('RESPONSE: {}'.format(data.decode()))
            self.__process_response(data)
            data, server = self.__sock.recvfrom(100)
            print('RESPONSE: {}'.format(data.decode()))
            self.__process_response(data)
        except socket.timeout:
            print('TIMEOUT')

    def __create_message(self, method_name, params):
        LightBulb.current_message_id += 1
        msg = {
            'id': LightBulb.current_message_id,
            'method': method_name,
            'params': params
        }
        return (json.dumps(msg) + '\r\n').encode()

    @staticmethod
    def parse_search_response(message):
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

    def __process_response(self, message):
        data = json.loads(message.decode())
        # only processing responses containing property values
        if 'method' in data and data['method'] == 'props':
            for param in data['params']:
                print(param)
                value = data['params'][param]
                print(value)
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

    @staticmethod
    def discover():
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)

        discovered = False
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, PORT))
        sock.settimeout(3)
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        try:
            while not discovered:
                print('Sending multicast message')
                sock.sendto(SEARCH_MESSAGE.encode(), (MULTICAST_IP, PORT))
                try:
                    data, server = sock.recvfrom(1024)
                except socket.timeout:
                    print('TIMEOUT')
                else:
                    discovered = True
                    parsed_msg = LightBulb.parse_search_response(data)
                    new_device = LightBulb(
                        id=parsed_msg['id'],
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
