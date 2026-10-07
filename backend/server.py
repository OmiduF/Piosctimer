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
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
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


def build_state() -> dict:
    now = time.time()
    return {
        "type": "state",
        "server_time": now,
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

    async def broadcast(self, message: dict):
        if not self.clients:
            return
        data = json.dumps(message)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


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
    url = f"http://{VMIX_HOST}:{VMIX_PORT}/api/"
    async with httpx.AsyncClient(timeout=VMIX_TIMEOUT) as client:
        while True:
            try:
                r = await client.get(url)
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


@app.on_event("startup")
async def on_startup():
    global osc_listening
    loop = asyncio.get_event_loop()

    dispatcher = Dispatcher()
    dispatcher.set_default_handler(osc_handler)

    # OSC bind must not be fatal: if the UDP port is busy or blocked, the
    # display (clock + WebSocket) should still come up instead of the whole
    # app failing to start.
    try:
        server = AsyncIOOSCUDPServer((OSC_HOST, OSC_PORT), dispatcher, loop)
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

    app.state.broadcast_task = asyncio.create_task(broadcast_loop())
    logger.info("WebSocket broadcast loop started")

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
    transport = getattr(app.state, "osc_transport", None)
    if transport:
        transport.close()
    if mongo_client:
        mongo_client.close()
