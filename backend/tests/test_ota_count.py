# OnTheAir player count (ota_count 1..4) tests: settings schema/validation/persistence,
# /api/status outputs length, connection close/reopen on unused ports (ss), HyperDeck EOF no-busy-loop.
import json
import os
import re
import socket
import subprocess
import threading
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SETTINGS_FILE = "/app/backend/settings.json"


def outs(base):
    return [{"name": f"Output {i + 1}", "port": base + i} for i in range(4)]


BASE = {
    "vmix_host": "172.16.50.25",
    "vmix_port": 8088,
    "osc_port": 7250,
    "ota_host": "127.0.0.1",
    "sources": {"casparcg": True, "vmix": True, "ota": True},
    "channels": [{"channel": 1, "layer": 10}, {"channel": 2, "layer": 10}],
}
API = dict(BASE, ota_mode="api", ota_outputs=outs(8081))
HD = dict(BASE, ota_mode="hyperdeck", ota_outputs=outs(9993))


def put(payload):
    return requests.put(f"{BASE_URL}/api/settings", json=payload, timeout=10)


def get_settings():
    return requests.get(f"{BASE_URL}/api/settings", timeout=10).json()


def ota():
    r = requests.get(f"{BASE_URL}/api/status", timeout=10)
    assert r.status_code == 200
    return r.json()["ota"]


def wait_for(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        o = ota()
        if pred(o):
            return o, True
        time.sleep(0.3)
    return ota(), False


def backend_pid():
    out = subprocess.check_output(["ss", "-tlnp"]).decode()
    for line in out.splitlines():
        if ":8001 " in line:
            # with --reload the listen socket is shared by the uvicorn parent; we want the worker
            procs = re.findall(r'\("([^"]+)",pid=(\d+)', line)
            workers = [int(p) for name, p in procs if name != "uvicorn"]
            if workers:
                return workers[0]
    raise RuntimeError("backend pid not found")


def established_ports(pid):
    """Remote ports of ESTABLISHED TCP connections owned by the backend worker."""
    out = subprocess.check_output(["ss", "-tnp", "state", "established"]).decode()
    ports = set()
    for line in out.splitlines():
        if f"pid={pid}," not in line:
            continue
        cols = line.split()
        peer = cols[3] if len(cols) > 3 else ""
        if peer.startswith("127.0.0.1:"):
            ports.add(int(peer.rsplit(":", 1)[1]))
    return ports


def wait_ports(pid, pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        p = established_ports(pid)
        if pred(p):
            return p, True
        time.sleep(0.5)
    return established_ports(pid), False


def cpu_seconds(pid):
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")


@pytest.fixture(scope="module", autouse=True)
def restore():
    yield
    put(dict(API, ota_count=3))


# Settings schema / validation / persistence
class TestCountSettings:
    def test_get_schema(self):
        d = get_settings()
        assert isinstance(d["ota_count"], int) and 1 <= d["ota_count"] <= 4
        assert len(d["ota_outputs"]) == 4

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_put_count_persists(self, n):
        r = put(dict(API, ota_count=n))
        assert r.status_code == 200, r.text
        assert r.json()["ota_count"] == n
        assert get_settings()["ota_count"] == n
        assert json.load(open(SETTINGS_FILE))["ota_count"] == n
        assert len(ota()["outputs"]) == n

    @pytest.mark.parametrize("n", [0, 5, -1])
    def test_invalid_count_422(self, n):
        put(dict(API, ota_count=2))
        assert put(dict(API, ota_count=n)).status_code == 422
        assert get_settings()["ota_count"] == 2

    def test_put_without_count_keeps(self):
        assert put(dict(API, ota_count=2)).status_code == 200
        r = put(API)
        assert r.status_code == 200 and r.json()["ota_count"] == 2

    def test_old_client_three_outputs(self):
        assert put(dict(API, ota_count=4)).status_code == 200
        r = put(dict(API, ota_outputs=outs(8081)[:3]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ota_count"] == 4 and len(d["ota_outputs"]) == 4
        assert d["ota_outputs"][3]["port"] == 8084


# HyperDeck mode count=1 + unused ports close / reopen
class TestHyperdeckCount:
    def test_count1_connected_and_decreasing(self):
        assert put(dict(HD, ota_count=1)).status_code == 200
        o, ok = wait_for(lambda o: len(o["outputs"]) == 1 and o["outputs"][0]["connected"]
                         and o["outputs"][0]["clip"]["status"] == "playing", 10)
        assert ok, o
        a = o["outputs"][0]["clip"]["time_left"]
        time.sleep(1.5)
        b = ota()["outputs"][0]["clip"]["time_left"]
        assert b < a or b > 30, (a, b)

    def test_unused_ports_closed_then_reopened(self):
        pid = backend_pid()
        assert put(dict(HD, ota_count=3)).status_code == 200
        p, ok = wait_ports(pid, lambda p: {9993, 9994, 9995} <= p)
        assert ok, p
        assert put(dict(HD, ota_count=1)).status_code == 200
        p, ok = wait_ports(pid, lambda p: 9993 in p and not ({9994, 9995} & p))
        assert ok, p
        time.sleep(3)  # make sure they don't come back
        p = established_ports(pid)
        assert not ({9994, 9995} & p), p
        assert put(dict(HD, ota_count=3)).status_code == 200
        p, ok = wait_ports(pid, lambda p: {9993, 9994, 9995} <= p)
        assert ok, p
        o, ok = wait_for(lambda o: len(o["outputs"]) == 3 and all(x["connected"] for x in o["outputs"]))
        assert ok, o


# REST API mode: unused ports should not keep keep-alive connections
class TestApiCount:
    def test_api_unused_ports_closed(self):
        # mock_ota_api.py is HTTP/1.0 (closes each request); real OnTheAir likely keeps
        # connections alive, so spin up an HTTP/1.1 keep-alive server for output 2.
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                body = json.dumps({"playback_status": "Playing", "item_display_name": "TEST_KA",
                                   "item_duration": 60.0, "item_elapsed": 1.0}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        srv.daemon_threads = True
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            pid = backend_pid()
            cfg = dict(API, ota_count=2)
            cfg["ota_outputs"] = [dict(o) for o in cfg["ota_outputs"]]
            cfg["ota_outputs"][1]["port"] = port
            assert put(cfg).status_code == 200
            p, ok = wait_ports(pid, lambda p: port in p)
            assert ok, p
            o, ok = wait_for(lambda o: o["outputs"][1]["connected"])
            assert ok, o
            assert put(dict(cfg, ota_count=1)).status_code == 200
            p, ok = wait_ports(pid, lambda p: port not in p, 10)
            assert ok, f"backend keeps ESTABLISHED keep-alive conn to unused API port {port}: {p}"
        finally:
            srv.shutdown()
            srv.server_close()


# Regression: HyperDeck server closing connection must not cause busy loop
class TestHyperdeckEOF:
    def test_eof_no_busy_loop(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(50)
        port = srv.getsockname()[1]
        stop = threading.Event()

        def serve():
            srv.settimeout(0.5)
            while not stop.is_set():
                try:
                    c, _ = srv.accept()
                except socket.timeout:
                    continue
                try:
                    c.sendall(b"500 connection info:\r\n\r\n")
                finally:
                    c.close()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        try:
            hd = dict(HD, ota_count=1)
            hd["ota_outputs"] = [dict(o) for o in hd["ota_outputs"]]
            hd["ota_outputs"][0]["port"] = port
            assert put(hd).status_code == 200
            o, ok = wait_for(lambda o: "closed the connection" in o["outputs"][0]["error"], 8)
            assert ok, o
            pid = backend_pid()
            c0, t0 = cpu_seconds(pid), time.time()
            time.sleep(5)
            cpu = (cpu_seconds(pid) - c0) / (time.time() - t0) * 100
            print(f"backend CPU during EOF: {cpu:.1f}%")
            assert cpu < 25, cpu
            assert not ota()["outputs"][0]["connected"]
        finally:
            stop.set()
            t.join(2)
            srv.close()
