from device import LightBulb
import time

if __name__ == "__main__":
    device = LightBulb.discover()
    print(device)
    device.connect()
    device.turn_on()
    time.sleep(2)
    device.set_hsv(300, 50)
    time.sleep(10)
    device.toggle()
