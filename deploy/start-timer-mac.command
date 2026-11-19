#!/usr/bin/env bash
# Timer CasparCG — pornire pe macOS (dublu-click în Finder).
# Pornește backend-ul și deschide afișajul fullscreen. Închide fereastra Terminal ca să oprești.

cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"

if [ ! -x "${ROOT}/backend/venv/bin/python" ]; then
  echo "[EROARE] Rulează întâi: bash deploy/install-mac.sh"
  read -r -p "Apasă Enter..."
  exit 1
fi

cd "${ROOT}/backend"
./venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
trap 'kill ${BACKEND_PID} 2>/dev/null' EXIT INT TERM

for _ in $(seq 1 30); do
  curl -s http://localhost:8001/api/status >/dev/null 2>&1 && break
  sleep 1
done

URL="http://localhost:8001"
CHROME="/Applications/Google Chrome.app"
if [ -d "${CHROME}" ]; then
  open -na "${CHROME}" --args --kiosk --app="${URL}" --no-first-run --user-data-dir="${HOME}/.timer-caspar-chrome"
else
  open "${URL}"
fi

echo "Timer pornit pe ${URL} (și din rețea pe http://$(ipconfig getifaddr en0 2>/dev/null || echo IP-MAC):8001)"
echo "Lasă fereastra deschisă. Ctrl+C sau închide fereastra ca să oprești."
wait ${BACKEND_PID}
