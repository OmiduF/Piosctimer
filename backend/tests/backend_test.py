"""Backend tests for Timer CasparCG OSC pipeline."""
import asyncio
import json
import os
import subprocess
import time

import pytest
import requests
import websockets
from pythonosc.udp_client import SimpleUDPClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL"
) else "http://localhost:8001"
# Direct backend for tests that need low latency / non-ingress
LOCAL_URL = "http://localhost:8001"
OSC_PORT = 7250


def _wait_idle(url=LOCAL_URL, timeout=5.0):
    """Wait until both channels report idle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{url}/api/status", timeout=3)
        if r.status_code == 200:
            data = r.json()
            if all(c["status"] == "idle" for c in data["channels"]):
                return data
        time.sleep(0.3)
    return None


# ---------------------------------------------------------------------------
# GET /api/status shape
# ---------------------------------------------------------------------------
class TestStatusEndpoint:
    def test_status_returns_expected_shape(self):
        r = requests.get(f"{BASE_URL}/api/status", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "state"
        assert "osc" in data
        assert data["osc"]["port"] == OSC_PORT
        assert "packets" in data["osc"]
        assert "connected" in data["osc"]
        assert isinstance(data["channels"], list) and len(data["channels"]) == 2
        ids = {c["id"] for c in data["channels"]}
        assert ids == {"ch1", "ch2"}
        for c in data["channels"]:
            for key in (
                "id",
                "channel",
                "layer",
                "filename",
                "elapsed",
                "total",
                "time_left",
                "status",
            ):
                assert key in c

    def test_idle_state_when_no_osc(self):
        # Ensure no sender is running, wait for idle timeout
        _wait_idle()
        r = requests.get(f"{BASE_URL}/api/status", timeout=5)
        data = r.json()
        for c in data["channels"]:
            assert c["status"] == "idle", f"expected idle, got {c}"
            assert c["time_left"] == 0
            assert c["total"] == 0


# ---------------------------------------------------------------------------
# OSC pipeline
# ---------------------------------------------------------------------------
class TestOSCPipeline:
    def test_osc_sender_updates_status(self):
        # Launch sender in background
        proc = subprocess.Popen(
            [
                "python",
                "test_osc_sender.py",
                "--host",
                "127.0.0.1",
                "--port",
                str(OSC_PORT),
            ],
            cwd="/app/backend",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(1.5)  # let a few packets arrive
            r = requests.get(f"{LOCAL_URL}/api/status", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert data["osc"]["packets"] > 0
            assert data["osc"]["connected"] is True
            ch1 = next(c for c in data["channels"] if c["id"] == "ch1")
            ch2 = next(c for c in data["channels"] if c["id"] == "ch2")
            assert ch1["status"] == "playing"
            assert ch1["filename"] == "opening_titles.mov"
            assert abs(ch1["total"] - 45.0) < 0.1
            assert abs(ch1["time_left"] - (ch1["total"] - ch1["elapsed"])) < 0.1
            assert ch2["status"] == "playing"
            assert ch2["filename"] == "commercial_break.mp4"
            assert abs(ch2["total"] - 20.0) < 0.1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        # Idle recovery
        time.sleep(2.5)
        r = requests.get(f"{LOCAL_URL}/api/status", timeout=5)
        for c in r.json()["channels"]:
            assert c["status"] == "idle"

    def test_live_status_when_total_zero(self):
        # Ensure idle first
        _wait_idle()
        client = SimpleUDPClient("127.0.0.1", OSC_PORT)
        # Send a name + time with total=0 => LIVE
        client.send_message("/channel/1/stage/layer/10/file/name", "live_feed.ts")
        client.send_message("/channel/1/stage/layer/10/file/time", [5.0, 0.0])
        time.sleep(0.6)
        r = requests.get(f"{LOCAL_URL}/api/status", timeout=5)
        ch1 = next(c for c in r.json()["channels"] if c["id"] == "ch1")
        assert ch1["status"] == "live", f"expected live, got {ch1}"
        assert ch1["filename"] == "live_feed.ts"
        # cleanup
        time.sleep(2.5)


# ---------------------------------------------------------------------------
# WebSocket streaming
# ---------------------------------------------------------------------------
class TestWebSocket:
    @pytest.mark.asyncio
    async def test_ws_streams_state_frames(self):
        ws_url = BASE_URL.replace("http", "ws") + "/api/ws"
        frames = []
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            # First frame should arrive immediately
            first = await asyncio.wait_for(ws.recv(), timeout=5)
            frames.append(json.loads(first))
            # Collect ~1.5s of frames
            end = time.time() + 1.5
            while time.time() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    frames.append(json.loads(msg))
                except asyncio.TimeoutError:
                    break
        assert len(frames) >= 3, f"expected multiple frames, got {len(frames)}"
        for f in frames:
            assert f["type"] == "state"
            assert "channels" in f and len(f["channels"]) == 2
