"""Dev tool: fake OnTheAir Video Express HyperDeck emulation on TCP 9993.

Usage: python mock_hyperdeck.py [port]
Plays clip 2 (90s) in a loop so the /ota display shows a live countdown.
"""
import asyncio
import sys
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9993
CLIPS = [("Intro Show.mov", 30), ("Reportaj Stiri.mov", 90)]
START = time.time()


def tc(sec: float, fps: int = 25) -> str:
    s = int(sec)
    fr = int((sec - s) * fps)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{fr:02d}"


async def handle(reader, writer):
    writer.write(b"500 connection info:\r\nprotocol version: 1.11\r\nmodel: OnTheAir Video Express\r\n\r\n")
    while line := await reader.readline():
        cmd = line.decode().strip()
        if cmd == "transport info":
            pos = (time.time() - START) % CLIPS[1][1]
            writer.write(
                (
                    "208 transport info:\r\nstatus: play\r\nspeed: 100\r\nslot id: 1\r\n"
                    f"clip id: 2\r\ndisplay timecode: {tc(pos)}\r\ntimecode: {tc(pos)}\r\n"
                    "video format: 1080i50\r\nloop: false\r\n\r\n"
                ).encode()
            )
        elif cmd == "clips get":
            body = "".join(
                f"{i}: {n} 00:00:00:00 {tc(d)}\r\n" for i, (n, d) in enumerate(CLIPS, 1)
            )
            writer.write(f"205 clips info:\r\nclip count: {len(CLIPS)}\r\n{body}\r\n".encode())
        else:
            writer.write(b"200 ok\r\n")
        await writer.drain()


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    print(f"Mock HyperDeck on :{PORT}")
    async with server:
        await server.serve_forever()


asyncio.run(main())
