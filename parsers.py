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
