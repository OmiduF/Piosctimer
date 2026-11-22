# OnTheAir 3-output tests: REST API mode (mock_ota_api.py 8081-8083) + HyperDeck mode
# (mock_hyperdeck.py 9993-9995) + settings API (ota_mode) tests.
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

API_OUTPUTS = [{"name": f"Output {i + 1}", "port": 8081 + i} for i in range(3)]
HD_OUTPUTS = [{"name": f"Output {i + 1}", "port": 9993 + i} for i in range(3)]
DEFAULT = {
    "vmix_host": "172.16.50.25",
    "vmix_port": 8088,
    "osc_port": 7250,
    "ota_host": "127.0.0.1",
    "ota_mode": "api",
    "sources": {"casparcg": True, "vmix": True, "ota": True},
    "ota_count": 3,
    "ota_outputs": API_OUTPUTS,
    "channels": [{"channel": 1, "layer": 10}, {"channel": 2, "layer": 10}],
}
HD = dict(DEFAULT, ota_mode="hyperdeck", ota_outputs=HD_OUTPUTS)
API_EXPECTED = {8081: 45.0, 8082: 65.0, 8083: 85.0}
HD_EXPECTED = {9993: 40.0, 9994: 65.0, 9995: 90.0}


def put(payload):
    return requests.put(f"{BASE_URL}/api/settings", json=payload, timeout=10)


def with_outputs(base=DEFAULT, **changes):
    outs = [dict(o) for o in base["ota_outputs"]]
    for idx, upd in changes.items():
        outs[int(idx[1:])].update(upd)
    return dict(base, ota_outputs=outs)


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


def all_connected(o):
    return all(x["connected"] for x in o["outputs"])


def titles_ok(prefix_fn):
    return lambda o: all_connected(o) and all(
        x["clip"]["title"] == prefix_fn(x["port"]) for x in o["outputs"])


@pytest.fixture(scope="module", autouse=True)
def restore():
    put(DEFAULT)
    wait_for(all_connected)
    yield
    put(DEFAULT)
    wait_for(all_connected)


# Settings GET/PUT with ota_mode + ota_outputs
class TestSettings:
    def test_get_settings_schema(self):
        d = requests.get(f"{BASE_URL}/api/settings", timeout=10).json()
        assert d["ota_host"] == "127.0.0.1"
        assert d["ota_mode"] == "api"
        assert d["ota_outputs"][:3] == API_OUTPUTS and d["ota_count"] == 3
        assert d["vmix_host"] == "172.16.50.25" and d["vmix_port"] == 8088
        assert d["osc_port"] == 7250 and len(d["channels"]) == 2

    @pytest.mark.parametrize("mode", ["foo", "API", "", 1])
    def test_invalid_mode_422(self, mode):
        r = put(dict(DEFAULT, ota_mode=mode))
        assert r.status_code == 422
        assert requests.get(f"{BASE_URL}/api/settings", timeout=10).json()["ota_mode"] == "api"

    def test_invalid_ota_host_422(self):
        assert put(dict(DEFAULT, ota_host="bad host;x")).status_code == 422

    @pytest.mark.parametrize("n", [0, 5])
    def test_wrong_outputs_length_422(self, n):
        assert put(dict(DEFAULT, ota_outputs=(API_OUTPUTS * 2)[:n])).status_code == 422

    def test_invalid_output_port_and_name_422(self):
        for bad in ({"port": 0}, {"port": 70000}, {"name": ""}, {"name": "x" * 41}):
            assert put(with_outputs(o1=bad)).status_code == 422, bad

    def test_rename_persists(self):
        r = put(with_outputs(o0={"name": "TEST_Studio A"}))
        assert r.status_code == 200 and r.json()["ota_outputs"][0]["name"] == "TEST_Studio A"
        f = json.loads(Path("/app/backend/settings.json").read_text())
        assert f["ota_outputs"][0]["name"] == "TEST_Studio A" and f["ota_mode"] == "api"
        time.sleep(0.5)
        assert all_connected(ota())
        assert put(DEFAULT).status_code == 200


# /api/status ota in REST API mode
class TestApiMode:
    def test_shape_and_clips(self):
        o, ok = wait_for(titles_ok(lambda p: f"Promo Meci {p}"))
        assert ok, o
        assert o["mode"] == "api" and o["host"] == "127.0.0.1"
        for i, out in enumerate(o["outputs"]):
            assert out["id"] == f"out{i + 1}" and out["port"] == 8081 + i
            c = out["clip"]
            assert c["status"] == "playing"
            assert abs(c["total"] - API_EXPECTED[out["port"]]) < 0.1
            assert abs(c["time_left"] - (c["total"] - c["elapsed"])) < 0.2

    def test_time_left_decreases(self):
        a = [x["clip"]["time_left"] for x in ota()["outputs"]]
        time.sleep(1.5)
        b = [x["clip"]["time_left"] for x in ota()["outputs"]]
        for i, port in enumerate((8081, 8082, 8083)):
            assert b[i] < a[i] or b[i] > API_EXPECTED[port] - 5, f"{port}: {a[i]} -> {b[i]}"

    def test_one_port_unreachable(self):
        assert put(with_outputs(o1={"port": 8089})).status_code == 200
        o, ok = wait_for(lambda o: not o["outputs"][1]["connected"] and o["outputs"][1]["error"], 5)
        assert ok, o
        assert o["outputs"][1]["clip"]["status"] == "idle"
        assert o["outputs"][1]["error"]
        print("error:", o["outputs"][1]["error"])
        time.sleep(3)
        top = subprocess.check_output(["top", "-b", "-n", "2", "-d", "1"]).decode()
        print([l for l in top.splitlines() if "python" in l][-5:])
        o = ota()
        assert o["outputs"][0]["connected"] and o["outputs"][2]["connected"]
        assert put(DEFAULT).status_code == 200
        o, ok = wait_for(all_connected, 6)
        assert ok, o


# Mode switching api <-> hyperdeck
class TestModeSwitch:
    def test_switch_to_hyperdeck_and_back(self):
        r = put(HD)
        assert r.status_code == 200 and r.json()["ota_mode"] == "hyperdeck"
        t0 = time.time()
        o, ok = wait_for(titles_ok(lambda p: f"Reportaj Stiri {p}.mov"), 10)
        assert ok, o
        print(f"switch to HD took {time.time() - t0:.1f}s")
        assert o["mode"] == "hyperdeck"
        for out in o["outputs"]:
            assert abs(out["clip"]["total"] - HD_EXPECTED[out["port"]]) < 0.1
        assert json.loads(Path("/app/backend/settings.json").read_text())["ota_mode"] == "hyperdeck"
        r = put(DEFAULT)
        assert r.status_code == 200 and r.json()["ota_mode"] == "api"
        t0 = time.time()
        o, ok = wait_for(titles_ok(lambda p: f"Promo Meci {p}"), 10)
        assert ok, o
        print(f"switch to API took {time.time() - t0:.1f}s")
        assert o["mode"] == "api"

    def test_api_mode_on_hyperdeck_ports_offline(self):
        # wrong combo: api mode pointed at HyperDeck TCP ports -> offline, not crash
        assert put(dict(DEFAULT, ota_outputs=HD_OUTPUTS)).status_code == 200
        o, ok = wait_for(lambda o: not any(x["connected"] for x in o["outputs"]), 6)
        assert ok, o
        print([x["error"] for x in o["outputs"]])
        assert put(DEFAULT).status_code == 200
        o, ok = wait_for(all_connected, 6)
        assert ok, o
