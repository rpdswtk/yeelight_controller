import socket
import threading
import time
import parser
from device import RgbLightBulb

IP = '239.255.255.250'
PORT = 1982
MESSAGE = '''M-SEARCH * HTTP/1.1\r\n
HOST: 239.255.255.250:1982\r\n
MAN: "ssdp:discover"\r\n
ST: wifi_bulb\r\n'''

IP2 = '192.168.0.241'

device_found = False


def send_search_msg():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((IP, PORT))
    global device_found
    while not device_found:
        print('SENDING search request')
        s.sendto(MESSAGE.encode(), (IP, PORT))
        time.sleep(3)


def listen():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((IP2, PORT))
    global device_found
    while not device_found:
        data, addr = s.recvfrom(1024)
        print('Received message: {}'.format(data))
        data = parser.parse_search_response(data)
        device = RgbLightBulb(data['id'], data['location'], data['power'],
                              data['brightness'], data['color_mode'],
                              data['color_temperature'], data['rgb'],
                              data['hue'], data['saturation'],
                              data['name'], data['fw_ver'])
        device_found = True
        print(device)


client_thread = threading.Thread(target=send_search_msg)
listen_thread = threading.Thread(target=listen)

if __name__ == "__main__":
    client_thread.start()
    listen_thread.start()
    while True:
        time.sleep(0.2)
