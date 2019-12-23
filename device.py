import socket
import struct
import parsers
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
            ['on', 'smooth', 500]
        )
        self.__send_message(msg)

    def turn_off(self):
        msg = self.__create_message(
            'set_power',
            ['off', 'smooth', 500]
        )
        print(msg)
        self.__send_message(msg)

    def __send_message(self, msg):
        try:
            print('SENDING MESSAGE: '.format(msg))
            self.__sock.send(msg)
            data, server = self.__sock.recvfrom(50)
            print('RESPONSE: {}'.format(data.decode()))
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
                    # print('Received message: {}'.format(data.decode()))

                    discovered = True
                    parsed_msg = parsers.parse_search_response(data)
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
