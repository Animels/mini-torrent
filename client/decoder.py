def parse_notation(string: bytes) -> str:
    notation = ""
    for s in string:
        char = bytes([s]).decode('utf-8')
        notation += char
        if char == ":":
            break
    return notation


def bytes_to_utf8(ibytes: bytes) -> str:
    return bytes(ibytes).decode('utf-8')


def decode_bencode(string: bytes, caret: int = 0) -> (any, int):
    mchar = bytes_to_utf8(string[caret:caret + 1])

    if mchar == "d":
        caret += 1
        result = {}
        while True:
            if bytes_to_utf8(string[caret:caret + 1]) == "e":
                caret += 1
                break
            key, caret = decode_bencode(string, caret)
            value, caret = decode_bencode(string, caret)
            result[key] = value

        return dict(result), caret

    elif mchar == "i":
        caret += 1
        myint = ""

        while True:
            if bytes_to_utf8(string[caret:caret + 1]) == "e":
                caret += 1
                break
            myint += bytes_to_utf8(string[caret:caret + 1])
            caret += 1

        return int(myint), caret

    elif mchar == "l":
        caret += 1
        mylist = []

        while True:
            if bytes_to_utf8(string[caret:caret + 1]) == "e":
                caret += 1
                break
            list_item, caret = decode_bencode(string, caret)
            mylist.append(list_item)

        return mylist, caret

    elif mchar.isdigit():
        length_wp = parse_notation(bytes(string[caret:]))
        length = int(length_wp.rstrip(":"))
        start = caret + len(length_wp)
        end = caret + len(length_wp) + int(length)
        try:
            result = bytes_to_utf8(string[start: end])
        except UnicodeDecodeError:
            result = string[start: end]

        caret += len(length_wp) + int(length)

        return result, caret
    else:
        raise ValueError(f"Invalid bencode character: {mchar}")


def encode_bencode(data):
    if isinstance(data, int):
        return f"i{data}e".encode("ascii")

    elif isinstance(data, list):
        encoded_list = b''.join(encode_bencode(item) for item in data)
        return b'l' + encoded_list + b'e'

    elif isinstance(data, dict):
        encoded_dict = b''.join(
            encode_bencode(k) + encode_bencode(v)
            for k, v in sorted(data.items())
        )
        return b'd' + encoded_dict + b'e'

    elif isinstance(data, str):
        data_bytes = data.encode('utf-8')
        return str(len(data_bytes)).encode('ascii') + b':' + data_bytes

    elif isinstance(data, bytes):
        return str(len(data)).encode('ascii') + b':' + data

    else:
        raise ValueError(f"Unsupported bencode type: {type(data)}")
