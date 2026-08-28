#!/usr/bin/env bash
# Launch Chromium in fullscreen kiosk mode pointing at the local backend.
# Used by the autostart entry (see KIOSK_SETUP.md).

set -e

URL="http://localhost:8001"

# Wait until the backend is up before opening the browser.
until curl -sf "${URL}/api/status" >/dev/null 2>&1; do
  sleep 1
done

# Prevent screen blanking / DPMS on the Pi display.
export DISPLAY=:0
xset s off || true
xset -dpms || true
xset s noblank || true

# Chromium binary name differs across Pi OS versions.
CHROME_BIN="$(command -v chromium-browser || command -v chromium)"

exec "${CHROME_BIN}" \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --app="${URL}"
