# Timer CasparCG (multi-channel) — PRD

## Original Problem
Fullscreen web display for a Raspberry Pi that reads CasparCG (2.5.x) playback state via OSC and shows a wall clock plus "time left" countdowns for two channels (layer 10 each), stacked vertically. CasparCG only sends OSC; it displays nothing. Backend listens on UDP, computes time-left, streams to a React kiosk display over WebSocket.

## Architecture
- **Backend (FastAPI, /app/backend/server.py)**: OSC UDP listener (python-osc, `AsyncIOOSCUDPServer`) on port 7250. Default handler parses `/channel/{c}/stage/layer/{l}/file/{time|frame|name|path}`. Computes `time_left = total - elapsed`. Broadcasts state to WebSocket clients every 200ms. Endpoints: `GET /api/status`, `WS /api/ws`.
- **Frontend (React, /app/frontend/src)**: `TimerDisplay.jsx` fullscreen black kiosk view; `useTimerSocket.js` WS hook with auto-reconnect. Clock ticks locally.
- **DB**: MongoDB present but not used yet (reserved for future settings persistence).
- **Config via backend/.env**: OSC_PORT=7250, CH1/CH2 CHANNEL+LAYER, IDLE_TIMEOUT=2.0.

## User Persona
Playout operator watching the Pi monitor for the clock and remaining time on ch1/ch2 layer 10.

## Core Requirements (static)
- Wall clock (top, large).
- Time left CH1 (layer 10) and CH2 (layer 10), stacked.
- Active filename shown next to each countdown.
- Warning colors: yellow < 30s, red < 10s (pulse + glow).
- Idle "--:--" when nothing on layer 10; LIVE "--:--" when duration unknown.
- Time format always MM:SS.

## Implemented (2026-06)
- Phase 1: OSC UDP listener verified parsing ch1/L10 + ch2/L10 (time/frame/name/path).
- Phase 2: time-left calc + WebSocket broadcast (200ms).
- Phase 3: React fullscreen display (clock + 2× time-left, warning colors, filenames, connection/OSC status footer).
- Idle + LIVE handling, WebSocket auto-reconnect.
- Dev tool: `backend/test_osc_sender.py` to simulate CasparCG OSC locally (not part of app).

## Backlog
- P1: Settings page (channel, layer, OSC port, font sizes) + MongoDB persistence.
- P2: More than 2 channels / configurable layers.
- P2: Sound alarms at countdown thresholds.
- P2: Kiosk autostart-at-boot docs + tablet/phone parallel access.

## CasparCG setup note
On the playout station's `casparcg.config`, add a `predefined-client` OSC pointing to the Pi's IP, port 7250.
