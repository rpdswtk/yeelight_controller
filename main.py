from yeelight_controller import LightBulb

if __name__ == "__main__":
    device = LightBulb.discover()
    print(device)
    device.connect()
    device.turn_on()
    device.set_brightness(10)
    device.set_temperature(5660)
    device.set_hsv(200, 60)
    device.toggle()
