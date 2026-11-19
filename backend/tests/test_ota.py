# OnTheAir 3-output (HyperDeck emulation) + settings API tests.
# Requires mock_hyperdeck.py on 127.0.0.1:9993/9994/9995
import json
import os
import subprocess
import time

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

OUTPUTS = [
    {"name": "Output 1", "port": 9993},
    {"name": "Output 2", "port": 9994},
    {"name": "Output 3", "port": 9995},
]
DEFAULT = {
    "vmix_host": "172.16.50.25",
    "vmix_port": 8088,
    "osc_port": 7250,
    "ota_host": "127.0.0.1",
    "ota_outputs": OUTPUTS,
    "channels": [{"channel": 1, "layer": 10}, {"channel": 2, "layer": 10}],
}
EXPECTED = {9993: 40.0, 9994: 65.0, 9995: 90.0}


def put(payload):
    return requests.put(f"{BASE_URL}/api/settings", json=payload, timeout=10)


def with_outputs(**changes):
    outs = [dict(o) for o in OUTPUTS]
    for idx, upd in changes.items():
        outs[int(idx[1:])].update(upd)
    return dict(DEFAULT, ota_outputs=outs)


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


@pytest.fixture(scope="module", autouse=True)
def restore():
    put(DEFAULT)
    wait_for(all_connected)
    yield
    put(DEFAULT)


# Settings GET/PUT with ota_outputs
class TestSettings:
    def test_get_settings_schema(self):
        d = requests.get(f"{BASE_URL}/api/settings", timeout=10).json()
        assert d["ota_host"] == "127.0.0.1"
        assert "ota_port" not in d
        assert d["ota_outputs"] == OUTPUTS
        assert d["vmix_host"] == "172.16.50.25" and d["vmix_port"] == 8088
        assert d["osc_port"] == 7250 and len(d["channels"]) == 2

    def test_invalid_ota_host_422(self):
        r = put(dict(DEFAULT, ota_host="bad host;x"))
        assert r.status_code == 422
        assert requests.get(f"{BASE_URL}/api/settings", timeout=10).json()["ota_host"] == "127.0.0.1"

    @pytest.mark.parametrize("n", [0, 1, 2, 4])
    def test_wrong_outputs_length_422(self, n):
        outs = (OUTPUTS * 2)[:n]
        r = put(dict(DEFAULT, ota_outputs=outs))
        assert r.status_code == 422

    def test_invalid_output_port_and_name_422(self):
        for bad in ({"port": 0}, {"port": 70000}, {"name": ""}, {"name": "x" * 41}):
            r = put(with_outputs(o1=bad))
            assert r.status_code == 422, bad

    def test_missing_ota_outputs_422(self):
        p = {k: v for k, v in DEFAULT.items() if k != "ota_outputs"}
        assert put(p).status_code == 422

    def test_rename_persists(self):
        r = put(with_outputs(o0={"name": "TEST_Studio A"}, o2={"name": "TEST_Studio C"}))
        assert r.status_code == 200
        assert r.json()["ota_outputs"][0]["name"] == "TEST_Studio A"
        d = requests.get(f"{BASE_URL}/api/settings", timeout=10).json()
        assert d["ota_outputs"][0]["name"] == "TEST_Studio A"
        assert d["ota_outputs"][2]["name"] == "TEST_Studio C"
        f = json.loads(open("/app/backend/settings.json").read())
        assert f["ota_outputs"][0]["name"] == "TEST_Studio A"
        names = [x["name"] for x in ota()["outputs"]]
        assert names == ["TEST_Studio A", "Output 2", "TEST_Studio C"]
        # rename must not disconnect
        time.sleep(0.5)
        assert all_connected(ota())
        assert put(DEFAULT).status_code == 200


# /api/status ota block with 3 outputs
class TestOtaStatus:
    def test_shape_and_clips(self):
        o, ok = wait_for(all_connected)
        assert ok, o
        assert o["host"] == "127.0.0.1"
        assert len(o["outputs"]) == 3
        for i, out in enumerate(o["outputs"]):
            for k in ("id", "name", "port", "connected", "error", "clip"):
                assert k in out
            assert out["id"] == f"out{i + 1}"
            port = 9993 + i
            assert out["port"] == port
            c = out["clip"]
            assert c["title"] == f"Reportaj Stiri {port}.mov"
            assert c["status"] == "playing"
            assert abs(c["total"] - EXPECTED[port]) < 0.1
            assert abs(c["time_left"] - (c["total"] - c["elapsed"])) < 0.1

    def test_time_left_decreases(self):
        a = [x["clip"]["time_left"] for x in ota()["outputs"]]
        time.sleep(1.5)
        b = [x["clip"]["time_left"] for x in ota()["outputs"]]
        for i, port in enumerate((9993, 9994, 9995)):
            assert b[i] < a[i] or b[i] > EXPECTED[port] - 5, f"{port}: {a[i]} -> {b[i]}"

    def test_output2_offline_and_back(self):
        r = put(with_outputs(o1={"port": 9999}))
        assert r.status_code == 200 and r.json()["ota_outputs"][1]["port"] == 9999
        o, ok = wait_for(lambda o: not o["outputs"][1]["connected"], 5)
        assert ok, o
        assert o["outputs"][1]["port"] == 9999 and o["outputs"][1]["clip"]["status"] == "idle"
        assert o["outputs"][0]["connected"] and o["outputs"][2]["connected"]
        # CPU must stay low while port unreachable
        time.sleep(3)
        pid = subprocess.check_output(["pgrep", "-f", "uvicorn server:app"]).split()
        cpus = []
        for p in pid:
            out = subprocess.check_output(["ps", "-o", "%cpu=", "-p", p.decode()]).decode().strip()
            cpus.append(float(out or 0))
        print("uvicorn cpu", cpus)
        top = subprocess.check_output(["top", "-b", "-n", "2", "-d", "1"]).decode()
        print([l for l in top.splitlines() if "python" in l][-4:])
        o = ota()
        assert o["outputs"][0]["connected"] and o["outputs"][2]["connected"]
        assert put(DEFAULT).status_code == 200
        t0 = time.time()
        o, ok = wait_for(all_connected, 8)
        assert ok, o
        print(f"reconnect took {time.time() - t0:.1f}s")
        assert time.time() - t0 < 4.5
