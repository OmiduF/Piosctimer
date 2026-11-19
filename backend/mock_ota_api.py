"""Dev tool: fake OnTheAir Video REST API (GET /playback/playing).

Usage: python mock_ota_api.py [port]   (default 8081)
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
DURATION = 45.0 + (PORT - 8081) * 20
START = time.time()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") != "/playback/playing":
            self.send_response(404)
            self.end_headers()
            return
        elapsed = (time.time() - START) % DURATION
        body = json.dumps(
            {
                "playback_status": "Playing",
                "playlist_index": 0,
                "playlist_display_name": "Playlist 1",
                "item_index": 2,
                "item_display_name": f"Promo Meci {PORT}",
                "item_duration": DURATION,
                "item_elapsed": round(elapsed, 3),
                "item_remaining": round(DURATION - elapsed, 3),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
