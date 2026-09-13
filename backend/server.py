import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

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
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/", StaticFiles(directory=str(FRONTEND_BUILD), html=True), name="static"
    )
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


@app.on_event("shutdown")
async def on_shutdown():
    task = getattr(app.state, "broadcast_task", None)
    if task:
        task.cancel()
    transport = getattr(app.state, "osc_transport", None)
    if transport:
        transport.close()
    if mongo_client:
        mongo_client.close()
