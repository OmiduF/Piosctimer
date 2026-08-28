"""Dev utility: simulate CasparCG 2.5.x OSC output for local pipeline testing.

Not part of the app. Run manually:
    python test_osc_sender.py --host 127.0.0.1 --port 7250
"""
import argparse
import time

from pythonosc.udp_client import SimpleUDPClient


def send_channel(client, channel, layer, filename, elapsed, total, fps=25.0):
    base = f"/channel/{channel}/stage/layer/{layer}/file"
    client.send_message(f"{base}/name", filename)
    client.send_message(f"{base}/path", f"C:/media/{filename}")
    client.send_message(f"{base}/time", [float(elapsed), float(total)])
    client.send_message(
        f"{base}/frame", [int(elapsed * fps), int(total * fps)]
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7250)
    args = ap.parse_args()

    client = SimpleUDPClient(args.host, args.port)
    print(f"Sending simulated CasparCG OSC to {args.host}:{args.port} (Ctrl+C to stop)")

    total1, total2 = 45.0, 20.0
    t = 0.0
    while True:
        e1 = t % total1
        e2 = t % total2
        send_channel(client, 1, 10, "opening_titles.mov", e1, total1)
        send_channel(client, 2, 10, "commercial_break.mp4", e2, total2)
        t += 0.2
        time.sleep(0.2)


if __name__ == "__main__":
    main()
