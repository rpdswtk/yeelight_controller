from device import LightBulb
import time

if __name__ == "__main__":
    device = LightBulb.discover()
    print(device)
    device.connect()
    device.turn_on()
    time.sleep(1)
    device.turn_off()
