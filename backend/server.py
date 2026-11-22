import asyncio
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import Literal

from pydantic import BaseModel, Field
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from starlette.middleware.cors import CORSMiddleware

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except Exception:  # motor/pymongo missing or incompatible -> Mongo is optional
    AsyncIOMotorClient = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OSC_PORT = int(os.environ.get("OSC_PORT", "7250"))
OSC_HOST = os.environ.get("OSC_HOST", "0.0.0.0")
IDLE_TIMEOUT = float(os.environ.get("IDLE_TIMEOUT", "2.0"))

CHANNELS = [
    {
        "id": "ch1",
        "channel": int(os.environ.get("CH1_CHANNEL", "1")),
        "layer": int(os.environ.get("CH1_LAYER", "10")),
    },
    {
        "id": "ch2",
        "channel": int(os.environ.get("CH2_CHANNEL", "2")),
        "layer": int(os.environ.get("CH2_LAYER", "10")),
    },
]

# vMix Web API (XML polling). vMix does not push; we poll http://host:port/api/
VMIX_HOST = os.environ.get("VMIX_HOST", "172.16.50.25")
VMIX_PORT = int(os.environ.get("VMIX_PORT", "8088"))

# OnTheAir Video Express (Softron) via its HyperDeck emulation (TCP 9993)
# Up to 3 outputs on the same Mac. Mode "api" = OnTheAir Video REST API
# (ports 8081/8082/8083), mode "hyperdeck" = HyperDeck emulation (9993...).
OTA_HOST = os.environ.get("OTA_HOST", "192.168.1.100")
OTA_MODE = os.environ.get("OTA_MODE", "api")
OTA_OUTPUTS = [
    {"id": f"out{i + 1}", "name": f"Output {i + 1}", "port": 8081 + i} for i in range(3)
]
OTA_POLL_INTERVAL = float(os.environ.get("OTA_POLL_INTERVAL", "0.3"))
OTA_TIMEOUT = float(os.environ.get("OTA_TIMEOUT", "2.0"))

# Runtime settings editable from the /settings page, persisted to settings.json
# (overrides .env values; survives git pull since the file is git-ignored).
SETTINGS_FILE = ROOT_DIR / "settings.json"
# Sources switched off in Settings send/listen to nothing on the network.
SOURCES = {"casparcg": True, "vmix": True, "ota": True}


def _load_settings():
    global VMIX_HOST, VMIX_PORT, OSC_PORT, OTA_HOST, OTA_MODE
    if not SETTINGS_FILE.exists():
        return
    try:
        data = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return
    VMIX_HOST = data.get("vmix_host", VMIX_HOST)
    VMIX_PORT = int(data.get("vmix_port", VMIX_PORT))
    OSC_PORT = int(data.get("osc_port", OSC_PORT))
    for k, v in data.get("sources", {}).items():
        if k in SOURCES:
            SOURCES[k] = bool(v)
    OTA_HOST = data.get("ota_host", OTA_HOST)
    # files saved before API mode existed were HyperDeck-only
    OTA_MODE = data.get("ota_mode", "hyperdeck" if "ota_host" in data else OTA_MODE)
    if "ota_port" in data:  # settings saved by the single-output version
        OTA_OUTPUTS[0]["port"] = int(data["ota_port"])
    for out, saved in zip(OTA_OUTPUTS, data.get("ota_outputs", [])):
        out["name"] = str(saved.get("name", out["name"]))[:40]
        out["port"] = int(saved.get("port", out["port"]))
    for cfg, saved in zip(CHANNELS, data.get("channels", [])):
        cfg["channel"] = int(saved.get("channel", cfg["channel"]))
        cfg["layer"] = int(saved.get("layer", cfg["layer"]))


def current_settings() -> dict:
    return {
        "vmix_host": VMIX_HOST,
        "vmix_port": VMIX_PORT,
        "osc_port": OSC_PORT,
        "sources": dict(SOURCES),
        "ota_host": OTA_HOST,
        "ota_mode": OTA_MODE,
        "ota_outputs": [{"name": o["name"], "port": o["port"]} for o in OTA_OUTPUTS],
        "channels": [
            {"id": c["id"], "channel": c["channel"], "layer": c["layer"]}
            for c in CHANNELS
        ],
    }


_load_settings()
VMIX_POLL_INTERVAL = float(os.environ.get("VMIX_POLL_INTERVAL", "0.3"))
VMIX_TIMEOUT = float(os.environ.get("VMIX_TIMEOUT", "2.0"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("timer-caspar")
logging.getLogger("httpx").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Mongo (kept minimal; persistence reserved for future settings page).
# Env vars are optional with sane defaults so the backend always boots even
# without a .env file (e.g. fresh Windows install) and even if Mongo is absent.
# ---------------------------------------------------------------------------
mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
db_name = os.environ.get("DB_NAME", "timer_caspar")
mongo_client = None
db = None
if AsyncIOMotorClient is not None:
    try:
        mongo_client = AsyncIOMotorClient(mongo_url)
        db = mongo_client[db_name]
    except Exception as exc:  # never block startup on Mongo
        logger.warning("MongoDB unavailable (%s); continuing without it", exc)

# ---------------------------------------------------------------------------
# Live OSC state
# key = (channel, layer) -> latest data received from CasparCG
# ---------------------------------------------------------------------------
osc_state: dict[tuple[int, int], dict] = {}
osc_packets_received = 0
osc_last_packet_ts = 0.0
osc_listening = False  # True once the UDP socket is bound successfully

ADDR_RE = re.compile(
    r"^/channel/(\d+)/stage/layer/(\d+)/(?:foreground/)?file/(time|frame|name|path)$"
)


def _basename(value: str) -> str:
    value = str(value).replace("\\", "/")
    return value.rsplit("/", 1)[-1]


def _entry(ch: int, ly: int) -> dict:
    return osc_state.setdefault(
        (ch, ly),
        {
            "elapsed": 0.0,
            "total": 0.0,
            "frame": 0,
            "frame_total": 0,
            "fps": 0.0,
            "filename": "",
            "last_update": 0.0,
        },
    )


def osc_handler(address: str, *args):
    """Default handler for every OSC message CasparCG pushes."""
    global osc_packets_received, osc_last_packet_ts
    osc_packets_received += 1
    osc_last_packet_ts = time.time()

    m = ADDR_RE.match(address)
    if not m:
        return

    ch, ly, field = int(m.group(1)), int(m.group(2)), m.group(3)
    e = _entry(ch, ly)

    try:
        if field == "time" and len(args) >= 2:
            e["elapsed"] = float(args[0])
            e["total"] = float(args[1])
        elif field == "frame" and len(args) >= 2:
            e["frame"] = int(args[0])
            e["frame_total"] = int(args[1])
        elif field in ("name", "path") and args:
            name = _basename(args[0])
            if name:
                e["filename"] = name
    except (ValueError, TypeError):
        return

    e["last_update"] = time.time()


def build_channel_payload(cfg: dict) -> dict:
    ch, ly = cfg["channel"], cfg["layer"]
    e = osc_state.get((ch, ly))
    now = time.time()

    base = {
        "id": cfg["id"],
        "channel": ch,
        "layer": ly,
        "filename": "",
        "elapsed": 0.0,
        "total": 0.0,
        "time_left": 0.0,
        "status": "idle",
    }

    if not e or (now - e["last_update"]) > IDLE_TIMEOUT:
        return base

    total = e["total"]
    elapsed = e["elapsed"]

    # No known duration (live input / stream) -> LIVE
    if total <= 0.05:
        base.update(
            {
                "filename": e["filename"],
                "status": "live",
            }
        )
        return base

    time_left = max(0.0, total - elapsed)
    base.update(
        {
            "filename": e["filename"],
            "elapsed": round(elapsed, 2),
            "total": round(total, 2),
            "time_left": round(time_left, 2),
            "status": "playing",
        }
    )
    return base


# ---------------------------------------------------------------------------
# vMix state (polled from the vMix Web API XML)
# ---------------------------------------------------------------------------
vmix_inputs: dict[str, dict] = {}
vmix_active = None   # program input number (string)
vmix_preview = None  # preview input number (string)
vmix_last_ok = 0.0
vmix_last_error = ""


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_vmix(xml_text: str):
    global vmix_inputs, vmix_active, vmix_preview
    root = ET.fromstring(xml_text)
    inputs = {}
    for inp in root.iter("input"):
        num = inp.get("number")
        if num is None:
            continue
        inputs[num] = {
            "title": inp.get("title", "") or inp.get("shortTitle", ""),
            "state": inp.get("state", ""),
            "position": _to_float(inp.get("position")),
            "duration": _to_float(inp.get("duration")),
        }
    vmix_inputs = inputs
    vmix_active = root.findtext("active")
    vmix_preview = root.findtext("preview")


def build_vmix_input_payload(role: str, number) -> dict:
    base = {
        "role": role,
        "number": number,
        "title": "",
        "elapsed": 0.0,
        "total": 0.0,
        "time_left": 0.0,
        "status": "idle",
    }
    if number is None:
        return base
    inp = vmix_inputs.get(str(number))
    if not inp:
        return base

    total = inp["duration"] / 1000.0
    elapsed = inp["position"] / 1000.0
    base["title"] = inp["title"]
    base["number"] = number

    # No duration (camera / NDI / live) -> LIVE
    if total <= 0.05:
        base["status"] = "live"
        return base

    base.update(
        {
            "elapsed": round(elapsed, 2),
            "total": round(total, 2),
            "time_left": round(max(0.0, total - elapsed), 2),
            "status": "playing",
        }
    )
    return base


def build_vmix_state() -> dict:
    now = time.time()
    connected = bool(vmix_last_ok and (now - vmix_last_ok) < 3.0)
    if not connected:
        return {
            "connected": False,
            "host": VMIX_HOST,
            "port": VMIX_PORT,
            "error": vmix_last_error,
            "program": build_vmix_input_payload("program", None),
            "preview": build_vmix_input_payload("preview", None),
        }
    return {
        "connected": True,
        "host": VMIX_HOST,
        "port": VMIX_PORT,
        "error": "",
        "program": build_vmix_input_payload("program", vmix_active),
        "preview": build_vmix_input_payload("preview", vmix_preview),
    }


# ---------------------------------------------------------------------------
# OnTheAir Video Express state (HyperDeck Ethernet protocol client)
# ---------------------------------------------------------------------------
ota_rt = [
    {"transport": {}, "clips": {}, "api": {}, "last_ok": 0.0, "last_error": "", "restart": asyncio.Event()}
    for _ in OTA_OUTPUTS
]

TC_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[:;.](\d{2})")
CLIP_RE = re.compile(
    r"^(\d+):\s*(.*?)\s+(?:(\d{2}:\d{2}:\d{2}[:;]\d{2})\s+)?(\d{2}:\d{2}:\d{2}[:;]\d{2})$"
)


def hd_fps(video_format: str) -> float:
    m = re.search(r"(\d+)([ip])(\d+)", video_format or "")
    if not m:
        return 25.0
    raw = m.group(3)
    rate = int(raw) / 100.0 if len(raw) > 2 else float(raw)
    if m.group(2) == "i":
        rate /= 2
    return rate if rate > 0 else 25.0


def tc_seconds(tc: str, fps: float) -> float:
    m = TC_RE.search(tc or "")
    if not m:
        return 0.0
    h, mi, se, fr = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + se + fr / max(1.0, round(fps))


def parse_hd_block(lines: list[str]) -> dict:
    out = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


async def hd_read_response(reader) -> tuple[int, list[str]]:
    """Read one HyperDeck response: header line + body until blank line."""
    raw = await reader.readline()
    if not raw:
        raise ConnectionError("HyperDeck closed the connection")
    header = raw.decode(errors="ignore").strip()
    if not header:
        return 0, []
    code = int(header.split(" ", 1)[0]) if header[:3].isdigit() else 0
    body = []
    if header.endswith(":"):
        while True:
            raw = await reader.readline()
            if not raw:
                raise ConnectionError("HyperDeck closed the connection")
            line = raw.decode(errors="ignore")
            if not line.strip():
                break
            body.append(line.strip())
    return code, body


async def hd_command(reader, writer, cmd: str, expect: int) -> list[str]:
    writer.write((cmd + "\r\n").encode())
    await writer.drain()
    while True:
        code, body = await asyncio.wait_for(hd_read_response(reader), OTA_TIMEOUT)
        if code == expect:
            return body
        if 100 <= code < 200:
            raise RuntimeError(f"HyperDeck error {code} for '{cmd}'")
        # skip async notifications (5xx) and blanks


def parse_hd_clips(body: list[str]) -> dict:
    clips = {}
    for line in body:
        m = CLIP_RE.match(line)
        if m:
            clips[m.group(1)] = {
                "name": m.group(2),
                "start": m.group(3) or "",
                "duration": m.group(4),
            }
    return clips


async def ota_api_poll(idx: int, client: httpx.AsyncClient):
    """REST API mode: poll GET /playback/playing until settings change."""
    out, rt = OTA_OUTPUTS[idx], ota_rt[idx]
    while not rt["restart"].is_set():
        r = await client.get(f"http://{OTA_HOST}:{out['port']}/playback/playing")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        rt["api"] = r.json()
        rt["last_ok"] = time.time()
        rt["last_error"] = ""
        try:
            await asyncio.wait_for(rt["restart"].wait(), OTA_POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def ota_poll_loop(idx: int):
    out, rt = OTA_OUTPUTS[idx], ota_rt[idx]
    client = httpx.AsyncClient(timeout=OTA_TIMEOUT)
    while True:
        writer = None
        rt["restart"].clear()
        if not SOURCES["ota"]:
            rt["last_ok"] = 0.0
            await rt["restart"].wait()
            continue
        try:
            if OTA_MODE == "api":
                await ota_api_poll(idx, client)
                continue
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(OTA_HOST, out["port"]), OTA_TIMEOUT
            )
            last_clips = 0.0
            while not rt["restart"].is_set():
                rt["transport"] = parse_hd_block(
                    await hd_command(reader, writer, "transport info", 208)
                )
                now = time.time()
                clip_id = rt["transport"].get("clip id", "")
                if now - last_clips > 3.0 or (clip_id and clip_id not in rt["clips"]):
                    rt["clips"] = parse_hd_clips(
                        await hd_command(reader, writer, "clips get", 205)
                    )
                    last_clips = now
                rt["last_ok"] = now
                rt["last_error"] = ""
                await asyncio.sleep(OTA_POLL_INTERVAL)
        except Exception as exc:
            rt["last_error"] = (str(exc) or type(exc).__name__)[:120]
            try:
                await asyncio.wait_for(rt["restart"].wait(), 2.0)
            except asyncio.TimeoutError:
                pass
        finally:
            if writer:
                writer.close()


def _num(d: dict, *keys) -> float:
    for k in keys:
        if isinstance(d.get(k), (int, float)):
            return float(d[k])
    return 0.0


def ota_clip_from_api(d: dict, clip: dict):
    """Map OnTheAir REST /playback/playing JSON (seconds) to our clip payload."""
    title = d.get("item_display_name") or d.get("item_name") or ""
    total = _num(d, "item_duration")
    elapsed = _num(d, "item_elapsed", "item_elapsed_time")
    remaining = _num(d, "item_remaining", "item_remaining_time") or max(0.0, total - elapsed)
    status = str(d.get("playback_status") or d.get("item_playback_status") or "").lower()
    if not title and not total:
        return
    clip.update(
        {
            "id": None,
            "title": title,
            "elapsed": round(elapsed, 2),
            "total": round(total, 2),
            "time_left": round(max(0.0, remaining), 2),
            "status": "live"
            if total <= 0.05
            else ("playing" if status.startswith("play") else "paused"),
        }
    )


def build_ota_output(idx: int) -> dict:
    out, rt = OTA_OUTPUTS[idx], ota_rt[idx]
    connected = bool(rt["last_ok"] and (time.time() - rt["last_ok"]) < 3.0)
    clip = {
        "id": None,
        "title": "",
        "elapsed": 0.0,
        "total": 0.0,
        "time_left": 0.0,
        "status": "idle",
    }
    state = {
        "id": out["id"],
        "name": out["name"],
        "port": out["port"],
        "connected": connected,
        "error": "" if connected else rt["last_error"],
        "clip": clip,
    }
    if not connected:
        return state

    if OTA_MODE == "api":
        ota_clip_from_api(rt["api"], clip)
        return state

    t = rt["transport"]
    clip_id = t.get("clip id", "")
    info = rt["clips"].get(clip_id)
    if not info or clip_id in ("", "none"):
        return state

    fps = hd_fps(t.get("video format", ""))
    total = tc_seconds(info["duration"], fps)
    start = tc_seconds(info["start"], fps)
    tc = tc_seconds(t.get("display timecode") or t.get("timecode", ""), fps)
    elapsed = tc - start if start and tc >= start else tc
    elapsed = min(max(0.0, elapsed), total)

    clip.update(
        {
            "id": clip_id,
            "title": info["name"],
            "elapsed": round(elapsed, 2),
            "total": round(total, 2),
            "time_left": round(max(0.0, total - elapsed), 2),
            "status": "live"
            if total <= 0.05
            else ("playing" if t.get("status") == "play" else "paused"),
        }
    )
    return state


def build_ota_state() -> dict:
    return {
        "host": OTA_HOST,
        "mode": OTA_MODE,
        "outputs": [build_ota_output(i) for i in range(len(OTA_OUTPUTS))],
    }


def build_state() -> dict:
    now = time.time()
    return {
        "type": "state",
        "server_time": now,
        "sources": dict(SOURCES),
        "osc": {
            "port": OSC_PORT,
            "host": OSC_HOST,
            "listening": osc_listening,
            "packets": osc_packets_received,
            "connected": bool(osc_last_packet_ts and (now - osc_last_packet_ts) < 5.0),
            "last_packet_age": round(now - osc_last_packet_ts, 2)
            if osc_last_packet_ts
            else None,
        },
        "channels": [build_channel_payload(cfg) for cfg in CHANNELS],
        "vmix": build_vmix_state(),
        "ota": build_ota_state(),
    }


# ---------------------------------------------------------------------------
# WebSocket broadcasting
# ---------------------------------------------------------------------------
class Broadcaster:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    async def _send(self, ws: WebSocket, data: str):
        try:
            await asyncio.wait_for(ws.send_text(data), 1.0)
        except Exception:
            # slow/frozen clients are dropped so nothing piles up in memory
            self.disconnect(ws)
            try:
                await asyncio.wait_for(ws.close(), 1.0)
            except Exception:
                pass

    async def broadcast(self, message: dict):
        if not self.clients:
            return
        data = json.dumps(message)
        await asyncio.gather(*(self._send(ws, data) for ws in list(self.clients)))


broadcaster = Broadcaster()


async def broadcast_loop():
    while True:
        try:
            await broadcaster.broadcast(build_state())
        except Exception as exc:  # keep the loop alive
            logger.error("broadcast_loop error: %s", exc)
        await asyncio.sleep(0.2)


async def vmix_poll_loop():
    """Poll the vMix Web API XML and keep program/preview state fresh."""
    global vmix_last_ok, vmix_last_error
    async with httpx.AsyncClient(timeout=VMIX_TIMEOUT) as client:
        while True:
            if not SOURCES["vmix"]:
                vmix_last_ok = 0.0
                await asyncio.sleep(1.0)
                continue
            try:
                r = await client.get(f"http://{VMIX_HOST}:{VMIX_PORT}/api/")
                if r.status_code == 200:
                    parse_vmix(r.text)
                    vmix_last_ok = time.time()
                    vmix_last_error = ""
                else:
                    vmix_last_error = f"HTTP {r.status_code}"
            except Exception as exc:
                vmix_last_error = str(exc)[:120]
            await asyncio.sleep(VMIX_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Timer CasparCG")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Timer CasparCG backend running"}


@api_router.get("/status")
async def status():
    return build_state()


class ChannelSettings(BaseModel):
    channel: int = Field(ge=1, le=999)
    layer: int = Field(ge=0, le=9999)


class OtaOutputSettings(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    port: int = Field(ge=1, le=65535)


class SourcesIn(BaseModel):
    casparcg: bool = True
    vmix: bool = True
    ota: bool = True


class SettingsIn(BaseModel):
    vmix_host: str = Field(min_length=1, max_length=255)
    vmix_port: int = Field(ge=1, le=65535)
    osc_port: int = Field(ge=1, le=65535)
    ota_host: str = Field(min_length=1, max_length=255)
    ota_mode: Literal["api", "hyperdeck"] | None = None
    sources: SourcesIn | None = None
    ota_outputs: list["OtaOutputSettings"] = Field(min_length=3, max_length=3)
    channels: list[ChannelSettings] = Field(min_length=2, max_length=2)


@api_router.get("/debug/mem")
async def debug_mem(start: bool = False):
    """Memory diagnostics: call with ?start=1, wait a few minutes, call again."""
    import resource
    import tracemalloc

    if start and not tracemalloc.is_tracing():
        tracemalloc.start(5)
    info = {
        "rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "ws_clients": len(broadcaster.clients),
        "asyncio_tasks": len(asyncio.all_tasks()),
        "tracing": tracemalloc.is_tracing(),
    }
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    info["rss_now_mb"] = round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    if tracemalloc.is_tracing():
        snap = tracemalloc.take_snapshot()
        info["top"] = [
            f"{st.size / 1024 / 1024:.1f} MB x{st.count} "
            + " <- ".join(f"{Path(fr.filename).name}:{fr.lineno}" for fr in reversed(st.traceback))
            for st in snap.statistics("traceback")[:8]
        ]
    return info


@api_router.get("/settings")
async def get_settings():
    return current_settings()


@api_router.put("/settings")
async def put_settings(body: SettingsIn):
    global VMIX_HOST, VMIX_PORT, vmix_last_ok, vmix_last_error
    global OTA_HOST, OTA_MODE
    host = body.vmix_host.strip()
    ota_host = body.ota_host.strip()
    for h in (host, ota_host):
        if not re.fullmatch(r"[A-Za-z0-9.\-]+", h):
            raise HTTPException(status_code=422, detail=f"IP/host invalid: {h}")
    mode = body.ota_mode or OTA_MODE
    new_sources = body.sources.model_dump() if body.sources else dict(SOURCES)
    if not any(new_sources.values()):
        raise HTTPException(status_code=422, detail="Cel puțin o sursă trebuie să fie pornită")
    ota_toggled = new_sources["ota"] != SOURCES["ota"]
    osc_toggled = new_sources["casparcg"] != SOURCES["casparcg"]
    SOURCES.update(new_sources)
    host_changed = ota_host != OTA_HOST or mode != OTA_MODE or ota_toggled
    OTA_HOST, OTA_MODE = ota_host, mode
    for out, rt, new in zip(OTA_OUTPUTS, ota_rt, body.ota_outputs):
        out["name"] = new.name.strip() or out["name"]
        if host_changed or new.port != out["port"]:
            out["port"] = new.port
            rt["last_ok"] = 0.0
            rt["restart"].set()
    if (host, body.vmix_port) != (VMIX_HOST, VMIX_PORT):
        VMIX_HOST, VMIX_PORT = host, body.vmix_port
        vmix_last_ok, vmix_last_error = 0.0, ""
    for cfg, new in zip(CHANNELS, body.channels):
        cfg["channel"], cfg["layer"] = new.channel, new.layer
    if body.osc_port != OSC_PORT or osc_toggled:
        await start_osc(body.osc_port)
    SETTINGS_FILE.write_text(json.dumps(current_settings(), indent=2))
    logger.info("Settings updated: %s", current_settings())
    return current_settings()


@api_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await broadcaster.connect(ws)
    try:
        # push initial snapshot immediately
        await ws.send_text(json.dumps(build_state()))
        while True:
            # we don't expect inbound messages; keep the socket open
            await ws.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
    except Exception:
        broadcaster.disconnect(ws)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# On the Raspberry Pi we build the React app into frontend/build and let the
# backend serve it, so the kiosk points at a single URL/port. In the Emergent
# preview this directory does not exist, so nothing changes there.
FRONTEND_BUILD = ROOT_DIR.parent / "frontend" / "build"
if FRONTEND_BUILD.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_BUILD / "static")),
        name="static",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve real files (favicon, manifest, ...) and fall back to index.html
        # for client-side routes like /vmix so deep links / refresh work.
        candidate = FRONTEND_BUILD / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_BUILD / "index.html"))

    logger.info("Serving React build from %s", FRONTEND_BUILD)


async def start_osc(port: int):
    """(Re)bind the OSC UDP listener. Failure is never fatal."""
    global osc_listening, OSC_PORT
    old = getattr(app.state, "osc_transport", None)
    if old:
        old.close()
        app.state.osc_transport = None
    OSC_PORT = port
    if not SOURCES["casparcg"]:
        osc_listening = False
        logger.info("CasparCG source disabled: OSC listener stopped")
        return
    dispatcher = Dispatcher()
    dispatcher.set_default_handler(osc_handler)
    try:
        server = AsyncIOOSCUDPServer(
            (OSC_HOST, OSC_PORT), dispatcher, asyncio.get_event_loop()
        )
        transport, _ = await server.create_serve_endpoint()
        app.state.osc_transport = transport
        osc_listening = True
        logger.info("OSC UDP listener started on %s:%s", OSC_HOST, OSC_PORT)
    except Exception as exc:
        app.state.osc_transport = None
        osc_listening = False
        logger.error(
            "Could not bind OSC UDP %s:%s (%s). "
            "App will run without OSC; check the port is free / firewall.",
            OSC_HOST,
            OSC_PORT,
            exc,
        )


@app.on_event("startup")
async def on_startup():
    await start_osc(OSC_PORT)

    app.state.broadcast_task = asyncio.create_task(broadcast_loop())
    logger.info("WebSocket broadcast loop started")

    app.state.ota_tasks = [
        asyncio.create_task(ota_poll_loop(i)) for i in range(len(OTA_OUTPUTS))
    ]
    logger.info(
        "OnTheAir (HyperDeck) poll loops started (%s ports %s)",
        OTA_HOST,
        [o["port"] for o in OTA_OUTPUTS],
    )

    app.state.vmix_task = asyncio.create_task(vmix_poll_loop())
    logger.info("vMix poll loop started (target %s:%s)", VMIX_HOST, VMIX_PORT)


@app.on_event("shutdown")
async def on_shutdown():
    task = getattr(app.state, "broadcast_task", None)
    if task:
        task.cancel()
    vmix_task = getattr(app.state, "vmix_task", None)
    if vmix_task:
        vmix_task.cancel()
    for t in getattr(app.state, "ota_tasks", []):
        t.cancel()
    transport = getattr(app.state, "osc_transport", None)
    if transport:
        transport.close()
    if mongo_client:
        mongo_client.close()
