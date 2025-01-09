import sys
import asyncio
from client.client import Client

torrent_client = Client(sys.argv[1])
asyncio.run(torrent_client.start())