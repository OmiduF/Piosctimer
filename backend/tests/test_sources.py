# Source on/off toggles (sources in /api/settings + /api/status): OSC socket, OTA polling, vMix polling.
import os
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ALL_ON = {"casparcg": True, "vmix": True, "ota": True}
DEFAULT = {
    "vmix_host": "172.16.50.25",
    "vmix_port": 8088,
    "osc_port": 7250,
    "ota_host": "127.0.0.1",
    "ota_mode": "api",
    "sources": ALL_ON,
    "ota_outputs": [{"name": f"Output {i + 1}", "port": 8081 + i} for i in range(3)],
    "channels": [{"channel": 1, "layer": 10}, {"channel": 2, "layer": 10}],
}


def put(payload):
    return requests.put(f"{BASE_URL}/api/settings", json=payload, timeout=10)


def status():
    return requests.get(f"{BASE_URL}/api/status", timeout=10).json()


def wait_for(pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        s = status()
        if pred(s):
            return s
        time.sleep(0.4)
    return status()


@pytest.fixture(autouse=True)
def restore():
    yield
    r = put(DEFAULT)
    assert r.status_code == 200


class TestSources:
    def test_status_and_settings_include_sources(self):
        assert put(DEFAULT).status_code == 200
        s = status()
        assert s["sources"] == ALL_ON
        g = requests.get(f"{BASE_URL}/api/settings", timeout=10).json()
        assert g["sources"] == ALL_ON

    def test_casparcg_off_closes_osc_then_reopens(self):
        r = put(dict(DEFAULT, sources={"casparcg": False, "vmix": True, "ota": True}))
        assert r.status_code == 200
        assert r.json()["sources"]["casparcg"] is False
        s = status()
        assert s["osc"]["listening"] is False
        assert s["sources"]["casparcg"] is False
        r = put(DEFAULT)
        assert r.json()["sources"]["casparcg"] is True
        assert status()["osc"]["listening"] is True

    def test_put_without_sources_keeps_current(self):
        off = {"casparcg": False, "vmix": False, "ota": True}
        assert put(dict(DEFAULT, sources=off)).status_code == 200
        payload = {k: v for k, v in DEFAULT.items() if k != "sources"}
        r = put(payload)
        assert r.status_code == 200
        assert r.json()["sources"] == off
        assert status()["sources"] == off
        assert status()["osc"]["listening"] is False

    def test_ota_off_disconnects_outputs_and_back_on(self):
        s = wait_for(lambda s: all(o["connected"] for o in s["ota"]["outputs"]))
        assert all(o["connected"] for o in s["ota"]["outputs"])
        assert put(dict(DEFAULT, sources={"casparcg": True, "vmix": True, "ota": False})).status_code == 200
        s = wait_for(lambda s: not any(o["connected"] for o in s["ota"]["outputs"]), 5)
        assert [o["connected"] for o in s["ota"]["outputs"]] == [False] * 3
        # stays disconnected (no polling)
        time.sleep(2)
        assert [o["connected"] for o in status()["ota"]["outputs"]] == [False] * 3
        assert put(DEFAULT).status_code == 200
        s = wait_for(lambda s: all(o["connected"] for o in s["ota"]["outputs"]))
        assert [o["connected"] for o in s["ota"]["outputs"]] == [True] * 3

    def test_ota_off_in_hyperdeck_mode(self):
        hd = dict(DEFAULT, ota_mode="hyperdeck",
                  ota_outputs=[{"name": f"Output {i + 1}", "port": 9993 + i} for i in range(3)])
        assert put(hd).status_code == 200
        s = wait_for(lambda s: all(o["connected"] for o in s["ota"]["outputs"]))
        assert all(o["connected"] for o in s["ota"]["outputs"])
        assert put(dict(hd, sources={"casparcg": True, "vmix": True, "ota": False})).status_code == 200
        s = wait_for(lambda s: not any(o["connected"] for o in s["ota"]["outputs"]), 5)
        assert not any(o["connected"] for o in s["ota"]["outputs"])

    def test_vmix_off(self):
        r = put(dict(DEFAULT, sources={"casparcg": True, "vmix": False, "ota": True}))
        assert r.status_code == 200
        s = status()
        assert s["sources"]["vmix"] is False
        assert s["vmix"]["connected"] is False

    def test_all_sources_off_backend_validation(self):
        # UI blocks this; check whether backend does too (informational)
        r = put(dict(DEFAULT, sources={"casparcg": False, "vmix": False, "ota": False}))
        print("ALL-OFF status:", r.status_code, r.text[:200])
        assert r.status_code in (200, 422)

    def test_invalid_sources_type_rejected(self):
        r = put(dict(DEFAULT, sources={"casparcg": "notabool", "vmix": True, "ota": True}))
        assert r.status_code == 422
