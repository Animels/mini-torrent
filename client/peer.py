import asyncio

from client.manager import PieceManager
from client.message import construct_request, construct_interested, construct_unchoke, construct_handshake


class Peer:
    def __init__(self, peer_id, info_hash, peer_info, meta_info, manager: PieceManager):
        self.peer_info = peer_info
        self.peer_id = peer_id
        self.info_hash = info_hash
        self.meta_info = meta_info
        self.piece_manager = manager
        self.pending_blocks = {}
        self.retry_pieces = asyncio.Queue()
        pass

    async def read_loop(self, reader):
        while True:
            try:
                length_bytes = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            except asyncio.IncompleteReadError:
                print("Peer disconnected.")
                break
            except (KeyboardInterrupt, asyncio.CancelledError):
                print('User interruption')
                break
            except Exception as e:
                print("Peer disconnected: ", e)
                break

            msg_len = int.from_bytes(length_bytes, "big")
            if msg_len == 0:
                continue

            msg_id_payload = await reader.readexactly(msg_len)
            msg_id = msg_id_payload[0]
            payload = msg_id_payload[1:]

            if msg_id == 7:  # PIECE
                piece_index = int.from_bytes(payload[0:4], "big")
                begin = int.from_bytes(payload[4:8], "big")
                block_data = payload[8:]

                key = (piece_index, begin)
                future = self.pending_blocks.get(key)
                if future:
                    future.set_result(block_data)
                    del self.pending_blocks[key]

    async def download_from_peer(self):
        reader = None
        writer = None
        read_task = None
        try:
            reader, writer, bit_field = await asyncio.wait_for(self.establish_connection(self.peer_info), timeout=20)
            if not reader or not writer:
                return

            read_task = asyncio.create_task(self.read_loop(reader))

            while not self.piece_manager.check_states():
                index = await self.piece_manager.get_qpiece()

                if self.piece_manager.get_pieces_state(index) != 0:
                    continue
                else:
                    if bit_field:
                        if not bit_field[5:][index // 8] & (1 << (7 - (index % 8))):
                            print('skip because bitfield')
                            continue

                    print('Try to download', index)
                    data, i = await self.download_piece(writer, index)
                    if data is not None and data != b'':
                        await self.piece_manager.put_completed_qpiece((i, data))
                        self.piece_manager.change_piece_state(index, 1)
                        print('Completed downloading piece', index)
                    else:
                        print('No data received')
                        self.piece_manager.change_piece_state(index, 0)

        except Exception as e:
            print(f"Error downloading from {self.peer_info}, need to retry: {e}")

        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()

            try:
                read_task.cancel()
            except Exception as e:
                pass

    async def download_piece(self, writer, index):
        piece_size = self.piece_manager.get_piece_size(index)
        piece_data = bytearray(piece_size)
        offset = 0

        tasks = []
        while offset < piece_size:
            block_len = min(2 ** 14, piece_size - offset)
            task = asyncio.create_task(self.fetch_block(writer, index, offset, block_len))
            tasks.append((offset, task))
            offset += block_len

        only_tasks = [t[1] for t in tasks]
        results = await asyncio.gather(*only_tasks)

        for (offset, _), block_data in zip(tasks, results):
            piece_data[offset: offset + len(block_data)] = block_data

        return bytes(piece_data), index

    async def fetch_block(self, writer, index, offset, block_len):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.pending_blocks[(index, offset)] = fut

        request_msg = construct_request(index, offset, block_len)
        writer.write(request_msg)
        await writer.drain()

        block_with_header = await asyncio.wait_for(fut, timeout=10)

        return block_with_header

    async def establish_connection(self, peer_info):
        ip, port = peer_info

        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=10)

            handshake_msg = construct_handshake(self.info_hash, self.peer_id)
            writer.write(handshake_msg)
            await writer.drain()

            handshake_recv = await reader.readexactly(68)
            if handshake_recv[28:48] != self.info_hash:
                return None, None, None

            bit_field = await reader.read(1024)

            interested_msg = construct_interested()
            writer.write(interested_msg)
            await writer.drain()

            response = await reader.read(1024)

            if construct_unchoke() == response:
                print(f"Connected to {ip}:{port}")
                return reader, writer, bit_field
            else:
                raise Exception(f"Tried connect to {ip}:{port}, server didn't unchoke")
        except Exception as e:
            print(f"Error connecting to {ip}:{port}: {e}")
            return None, None, None
