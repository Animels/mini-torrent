from struct import pack

KEEP_ALIVE = b''
CHOKE = b'\x00'
UNCHOKE = b'\x01'
INTERESTED = b'\x02'
NOT_INTERESTED = b'\x03'
HAVE = b'\x04'
BIT_FIELD = b'\x05'
REQUEST = b'\x06'
PIECE = b'\x07'
CANCEL = b'\x08'
PORT = b'\x09'

def construct_message(msg: bytes, index=None, begin=None, length=None) -> bytes:
    msg_length = pack('>I', len(msg))
    if index is not None:
        index_byte = pack('>I', index)
        begin_byte = pack('>I', begin)
        length_byte = pack('>I', length)
        total_length = pack('>I', len(msg + index_byte + begin_byte + length_byte))
        return total_length + msg + index_byte + begin_byte + length_byte

    return msg_length + msg


def construct_request(index, offset, block_len):
    return construct_message(REQUEST, index, offset, block_len)

def construct_interested():
    return construct_message(INTERESTED)

def construct_unchoke():
    return construct_message(UNCHOKE)

def construct_handshake(info_hash, peer_id):
    handshake_msg = (
                    b'\x13BitTorrent protocol'
                    + b'\x00\x00\x00\x00\x00\x00\x00\x00'
                    + info_hash
                    + peer_id.encode("utf-8")
            )
    return handshake_msg
