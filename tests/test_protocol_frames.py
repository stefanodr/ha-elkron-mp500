"""Frame reader: a stray 0x03 (seen while the alarm sounded) must be skipped."""
import asyncio
import sys

sys.path.insert(0, ".")
from custom_components.elkron_mp500.protocol import ElkronTcpClient


async def main():
    client = ElkronTcpClient("x", 5555)
    reader = asyncio.StreamReader()
    reader.feed_data(b"\x03\x03\x06")
    assert await client._read_response(reader) == b"\x06"
    print("stray 0x03 skipped: OK")


asyncio.run(main())
