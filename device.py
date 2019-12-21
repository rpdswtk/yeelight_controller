class RgbLightBulb:

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
