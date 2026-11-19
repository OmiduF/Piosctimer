# OnTheAir (HyperDeck emulation) + settings API tests. Requires mock_hyperdeck.py on 127.0.0.1:9993
import os
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

DEFAULT = {
    "vmix_host": "172.16.50.25",
    "vmix_port": 8088,
    "osc_port": 7250,
    "ota_host": "127.0.0.1",
    "ota_port": 9993,
    "channels": [{"channel": 1, "layer": 10}, {"channel": 2, "layer": 10}],
}


def status():
    r = requests.get(f"{BASE_URL}/api/status", timeout=10)
    assert r.status_code == 200
    return r.json()


def wait_ota(connected, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        o = status()["ota"]
        if o["connected"] is connected:
            return o, True
        time.sleep(0.3)
    return status()["ota"], False


@pytest.fixture(scope="module", autouse=True)
def restore():
    requests.put(f"{BASE_URL}/api/settings", json=DEFAULT, timeout=10)
    wait_ota(True)
    yield
    requests.put(f"{BASE_URL}/api/settings", json=DEFAULT, timeout=10)


# Settings GET/PUT including OTA
class TestSettings:
    def test_get_settings_has_ota(self):
        d = requests.get(f"{BASE_URL}/api/settings", timeout=10).json()
        assert d["ota_host"] == "127.0.0.1"
        assert d["ota_port"] == 9993
        assert d["vmix_host"] == "172.16.50.25" and d["vmix_port"] == 8088
        assert d["osc_port"] == 7250 and len(d["channels"]) == 2

    def test_invalid_ota_host_422(self):
        p = dict(DEFAULT, ota_host="bad host;x")
        r = requests.put(f"{BASE_URL}/api/settings", json=p, timeout=10)
        assert r.status_code == 422
        assert requests.get(f"{BASE_URL}/api/settings", timeout=10).json()["ota_host"] == "127.0.0.1"

    def test_invalid_ota_port_422(self):
        for port in (0, 70000):
            r = requests.put(f"{BASE_URL}/api/settings", json=dict(DEFAULT, ota_port=port), timeout=10)
            assert r.status_code == 422

    def test_missing_ota_fields_422(self):
        p = {k: v for k, v in DEFAULT.items() if k not in ("ota_host", "ota_port")}
        r = requests.put(f"{BASE_URL}/api/settings", json=p, timeout=10)
        assert r.status_code == 422

    def test_settings_file_persisted(self):
        import json
        data = json.loads(open("/app/backend/settings.json").read())
        assert data["ota_host"] == "127.0.0.1" and data["ota_port"] == 9993


# OTA status block
class TestOtaStatus:
    def test_ota_block_shape_and_connected(self):
        o, ok = wait_ota(True)
        assert ok, o
        for k in ("connected", "host", "port", "error", "clip"):
            assert k in o
        assert o["host"] == "127.0.0.1" and o["port"] == 9993
        c = o["clip"]
        assert c["id"] == "2"
        assert c["title"] == "Reportaj Stiri.mov"
        assert c["status"] == "playing"
        assert abs(c["total"] - 90.0) < 0.1
        assert abs(c["time_left"] - (c["total"] - c["elapsed"])) < 0.1

    def test_time_left_decreases(self):
        a = status()["ota"]["clip"]["time_left"]
        time.sleep(1.5)
        b = status()["ota"]["clip"]["time_left"]
        # Allow loop wraparound (mock loops every 90s)
        assert b < a or b > 85, f"{a} -> {b}"

    def test_live_switch_port_offline_and_back(self):
        r = requests.put(f"{BASE_URL}/api/settings", json=dict(DEFAULT, ota_port=9999), timeout=10)
        assert r.status_code == 200 and r.json()["ota_port"] == 9999
        o, ok = wait_ota(False, 5)
        assert ok, o
        assert o["port"] == 9999 and o["clip"]["status"] == "idle"
        r = requests.put(f"{BASE_URL}/api/settings", json=DEFAULT, timeout=10)
        assert r.status_code == 200
        t0 = time.time()
        o, ok = wait_ota(True, 8)
        assert ok, o
        print(f"reconnect took {time.time() - t0:.1f}s")
        assert time.time() - t0 < 4.5
