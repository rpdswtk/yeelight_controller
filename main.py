from yeelight_controller import LightBulb
import time

if __name__ == "__main__":
    device = LightBulb.discover()
    device.turn_on()
    device.set_brightness(10)
    device.set_temperature(5660)
    device.set_hsv(200, 60)
    time.sleep(3)
    device.toggle()
