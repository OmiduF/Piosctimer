#!/usr/bin/env bash
#
# Timer CasparCG — instalare pe macOS (o singură dată).
#     bash deploy/install-mac.sh
#
# Necesită: Python 3 (python.org sau Homebrew) și Node.js (nodejs.org sau Homebrew).
# Creează venv-ul backend și buildează frontend-ul. Pornirea: deploy/start-timer-mac.command

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

command -v python3 >/dev/null 2>&1 || { echo "[EROARE] Lipsește python3. Instalează de pe https://www.python.org/downloads/macos/ sau: brew install python"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[EROARE] Lipsește Node.js. Instalează de pe https://nodejs.org (LTS) sau: brew install node"; exit 1; }

echo "==> [1/3] Backend (venv + pip)..."
cd "${PROJECT_DIR}/backend"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements-run.txt

if [ ! -f .env ]; then
  cat > .env <<EOF
CORS_ORIGINS="*"
OSC_PORT=7250
OSC_HOST=0.0.0.0
EOF
fi

echo "==> [2/3] Frontend (build)..."
cd "${PROJECT_DIR}/frontend"
command -v yarn >/dev/null 2>&1 || npm install -g yarn || sudo npm install -g yarn
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn install
yarn build

echo "==> [3/3] Script de pornire..."
chmod +x "${PROJECT_DIR}/deploy/start-timer-mac.command"

echo
echo "Gata! Pornește cu dublu-click pe: deploy/start-timer-mac.command"
echo "La prima pornire, macOS poate cere voie pentru conexiuni de rețea: alege Allow."
