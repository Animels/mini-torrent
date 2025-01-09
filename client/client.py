import asyncio

from urllib.parse import quote_from_bytes
from random import randint
from socket import inet_ntoa
from requests import get
from client.decoder import decode_bencode
from hashlib import sha1
from client.manager import PieceManager, WriteManager
from client.peer import Peer
from client.torrentfile import TorrentFile


def generate_peer_id():
    return '-PC0001-' + ''.join([str(randint(0, 9)) for _ in range(12)])


def parse_peers(peers: bytes):
    peers_list = []
    for i in range(0, len(peers), 6):
        ip = inet_ntoa(peers[i: i + 4])
        port = int.from_bytes(peers[i + 4: i + 6], 'big')
        peers_list.append((ip, port))
    return peers_list


class Client:
    def __init__(self, file_name):
        self.file = TorrentFile(file_name)
        self.peer_id = generate_peer_id()
        self.info_hash = sha1(self.file.get_bencoded_info()).digest()
        self.piece_manager = PieceManager(self.file)
        self.write_manager = WriteManager(self.file, self.piece_manager)
        self.init = False

    async def start(self):
        await self.write_manager.resume_writing()
        self.init = True

        while True:
            decoded_res = self.get_announce()
            peers = parse_peers(decoded_res['peers'])

            try:
                await self.initiate_download(peers)
            except Exception as e:
                print("Failed download with", e)
            finally:
                if (self.piece_manager.get_pieces_states().find(0) == -1
                        and self.piece_manager.get_pieces_states().find(1) == -1):
                    print("All pieces are complete.")
                    break
                else:
                    await self.write_manager.resume_writing()
                    print("Still have incomplete pieces, re-trying...")

    async def initiate_download(self, peers_info):
        self.piece_manager.recalculate_states()

        peers = [Peer(self.peer_id, self.info_hash, peer_info, self.file.get_info(), self.piece_manager) for peer_info in peers_info]
        tasks = [
                    asyncio.create_task(peer.download_from_peer())
                    for peer in peers
                ] + [asyncio.create_task(self.write_manager.write_file())]

        await asyncio.gather(*tasks)

    def get_announce(self):
        urlencoded_info = quote_from_bytes(self.info_hash)
        query_params = {
            'info_hash': urlencoded_info,
            'peer_id': self.peer_id,
            'downloaded': "0",
            'uploaded': "0",
            'left': f'{self.file.get_total_length()}',
            'port': "6881",
            'compact': "1"
        }
        query_string = "&".join(f"{key}={value}" for key, value in query_params.items())
        trim_url = self.file.get_announce().split('?')
        full_url = f"{trim_url[0]}?{query_string}"

        res = get(full_url)
        decoded_res, _ = decode_bencode(res.content)
        return decoded_res
