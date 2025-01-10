import asyncio
import os.path

from math import ceil
from hashlib import sha1

from client.torrentfile import TorrentFile


class PieceManager:
    def __init__(self, file: TorrentFile):
        self.piece_length = file.get_piece_length()
        self.total_length = file.get_total_length()
        self.total_pieces = ceil(self.total_length / self.piece_length)
        self.piece_states = bytearray(self.total_pieces)
        self.piece_queue = asyncio.Queue()
        self.completed_pieces = asyncio.Queue()
        print('Piece length: ', self.piece_length)
        print('Total length: ', self.total_length)
        print('Total pieces: ', self.total_pieces)

    def recalculate_states(self):
        for index in range(self.total_pieces):
            if self.piece_states[index] == 0 or self.piece_states[index] == 1:
                self.piece_states[index] = 0
                self.piece_queue.put_nowait(index)

    def change_piece_state(self, index, state):
        self.piece_states[index] = state

    def get_pieces_states(self):
        return self.piece_states

    def get_pieces_state(self, index):
        return self.piece_states[index]

    def is_piece_queue_empty(self):
        return self.piece_queue.empty()

    async def put_qpiece(self, piece):
        await self.piece_queue.put(piece)

    async def get_qpiece(self):
        return await asyncio.wait_for(self.piece_queue.get(),timeout=10)

    async def put_completed_qpiece(self, piece):
        await self.completed_pieces.put(piece)

    async def get_completed_qpiece(self):
        return await asyncio.wait_for(self.completed_pieces.get(),timeout=10)

    def get_piece_size(self, index):
        start = index * self.piece_length
        end = start + self.piece_length

        if end > self.total_length:
            end = self.total_length

        return end - start

    def check_states(self):
        return self.get_pieces_states().find(0) == -1 and self.get_pieces_states().find(1) == -1


file_lock = asyncio.Lock()


class WriteManager:
    def __init__(self, file: TorrentFile, piece_manager: PieceManager):
        self.piece_manager = piece_manager
        self.file = file
        self.written_pieces = 0

        if not os.path.exists(self.file.get_file_name()):
            f = open(self.file.get_file_name(), 'wb')
            total_size = self.file.get_total_length()
            f.seek(total_size - 1)
            f.write(b"\0")

    async def write_file(self):
        with open(self.file.get_file_name(), 'r+b') as source_f:
            async with file_lock:
                while self.written_pieces < self.piece_manager.total_pieces:
                    try:
                        index, data = await self.piece_manager.get_completed_qpiece()
                    except asyncio.TimeoutError:
                        if self.piece_manager.check_states():
                            break
                        else:
                            continue

                    if not data:
                        print("No data received, stopping file writing.")
                        break

                    expected_sha = self.file.get_pieces()[20 * index: 20 * (index + 1)]
                    if expected_sha != sha1(data).digest():
                        self.piece_manager.change_piece_state(index, 0)
                        continue
                    else:
                        position = index * self.file.get_piece_length()

                        source_f.seek(position)
                        source_f.write(data)
                        source_f.flush()

                        print(f"Inserted piece {index} at position {position}, data length: {len(data)}")

                        self.piece_manager.change_piece_state(index, 2)
                        self.written_pieces += 1
                        percent = round((100 / self.piece_manager.total_pieces) * self.written_pieces, 2)
                        print(f"Total pieces written so far: {percent}%")
                return

    async def resume_writing(self):
        print("Resuming writing.")
        piece_index = 0
        with open(self.file.get_file_name(), 'r+b') as source_f:
            async with file_lock:
                while True:
                    position = piece_index * self.file.get_piece_length()
                    source_f.seek(position)
                    data = source_f.read(self.file.get_piece_length())
                    expected_sha = self.file.get_pieces()[20 * piece_index: 20 * (piece_index + 1)]
                    if sha1(data).digest() == expected_sha:
                        self.piece_manager.change_piece_state(piece_index, 2)
                        self.written_pieces += 1
                    else:
                        self.piece_manager.change_piece_state(piece_index, 0)

                    piece_index += 1
                    if piece_index == self.piece_manager.total_pieces:
                        percent = round((100 / self.piece_manager.total_pieces) * self.written_pieces, 2)
                        print(
                            f"Total pieces written so far: {percent}%")
                        break
        self.piece_manager.recalculate_states()
