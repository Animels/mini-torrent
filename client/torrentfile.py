from client.decoder import decode_bencode, encode_bencode


class TorrentFile:
    def __init__(self, file_name):
        with open(file_name, 'rb') as f:
            self.bencoded_file = f.read()
        self.decoded_file, _ = decode_bencode(self.bencoded_file)

    def get_bencoded_file(self):
        return self.bencoded_file

    def get_decoded_file(self):
        return self.decoded_file

    def get_file_name(self):
        return self.decoded_file['info']['name']

    def get_announce(self):
        return self.decoded_file['announce']

    def get_info(self):
        return self.decoded_file['info']

    def get_bencoded_info(self):
        return encode_bencode(self.decoded_file['info'])

    def get_piece_length(self):
        return self.decoded_file['info']['piece length']

    def get_total_length(self):
        if 'files' in self.decoded_file['info']:
            raise Exception('Do not support multifile')
        return self.decoded_file['info']['length']

    def get_pieces(self):
        return self.decoded_file['info']['pieces']

    def get_amount_pieces(self):
        return self.decoded_file['info']['amount pieces']
