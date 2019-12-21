def parse_search_response(message):
    parsed_data = dict()
    splitted = message.decode().split('\r\n')
    parsed_data['location'] = splitted[4].split('//')[1]
    parsed_data['id'] = splitted[6].split(' ')[1]
    parsed_data['model'] = splitted[7].split(' ')[1]
    parsed_data['fw_ver'] = splitted[8].split(' ')[1]
    parsed_data['power'] = splitted[10].split(' ')[1]
    parsed_data['brightness'] = splitted[11].split(' ')[1]
    parsed_data['color_mode'] = splitted[12].split(' ')[1]
    parsed_data['color_temperature'] = splitted[13].split(' ')[1]
    parsed_data['rgb'] = splitted[14].split(' ')[1]
    parsed_data['hue'] = splitted[15].split(' ')[1]
    parsed_data['saturation'] = splitted[16].split(' ')[1]
    parsed_data['name'] = splitted[17].split(' ')[1]
    return parsed_data
