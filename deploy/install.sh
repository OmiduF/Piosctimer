#!/usr/bin/env bash
#
# Timer CasparCG — instalare automată pe Raspberry Pi.
# Rulează O SINGURĂ comandă din rădăcina proiectului:
#
#     bash deploy/install.sh
#
# Ce face: instalează pachetele, creează venv-ul backend, buildează frontend-ul,
# înregistrează serviciul systemd (boot) și configurează Chromium în kiosk la boot.
# Este idempotent: îl poți rula de mai multe ori fără probleme.

set -euo pipefail

# ---------------------------------------------------------------------------
# Detectare cale proiect + utilizator
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"
USER_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"
BACKEND_URL="http://localhost:8001"

echo "==> Proiect : ${PROJECT_DIR}"
echo "==> User    : ${RUN_USER}"
echo "==> URL app : ${BACKEND_URL}"
echo

# ---------------------------------------------------------------------------
# 1. Pachete de sistem
# ---------------------------------------------------------------------------
echo "==> [1/6] Instalare pachete de sistem..."
sudo apt-get update -y
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  chromium-browser x11-xserver-utils curl ca-certificates

# Node.js + yarn (pentru build-ul frontend)
if ! command -v node >/dev/null 2>&1; then
  echo "==> Instalare Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
if ! command -v yarn >/dev/null 2>&1; then
  sudo npm install -g yarn
fi

# ---------------------------------------------------------------------------
# 2. Backend: virtualenv + dependențe
# ---------------------------------------------------------------------------
echo "==> [2/6] Configurare backend (venv + pip)..."
cd "${PROJECT_DIR}/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip
if [ -f requirements-run.txt ]; then
  ./venv/bin/pip install -r requirements-run.txt
else
  ./venv/bin/pip install -r requirements.txt
fi

# .env implicit dacă lipsește
if [ ! -f .env ]; then
  cat > .env <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
OSC_PORT=7250
OSC_HOST=0.0.0.0
IDLE_TIMEOUT=2.0
CH1_CHANNEL=1
CH1_LAYER=10
CH2_CHANNEL=2
CH2_LAYER=10
EOF
fi

# ---------------------------------------------------------------------------
# 3. Frontend: build servit de backend
# ---------------------------------------------------------------------------
echo "==> [3/6] Build frontend React..."
cd "${PROJECT_DIR}/frontend"
echo "REACT_APP_BACKEND_URL=${BACKEND_URL}" > .env
yarn install
yarn build

# ---------------------------------------------------------------------------
# 4. Serviciu systemd pentru backend (pornire la boot)
# ---------------------------------------------------------------------------
echo "==> [4/6] Înregistrare serviciu systemd..."
sudo tee /etc/systemd/system/timer-caspar-backend.service >/dev/null <<EOF
[Unit]
Description=Timer CasparCG backend (OSC + WebSocket + serves React build)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}/backend
ExecStart=${PROJECT_DIR}/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now timer-caspar-backend

# ---------------------------------------------------------------------------
# 5. Kiosk autostart (Chromium fullscreen la login)
# ---------------------------------------------------------------------------
echo "==> [5/6] Configurare kiosk autostart..."
chmod +x "${PROJECT_DIR}/deploy/start-kiosk.sh"

AUTOSTART_DIR="${USER_HOME}/.config/autostart"
mkdir -p "${AUTOSTART_DIR}"
cat > "${AUTOSTART_DIR}/timer-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Timer CasparCG Kiosk
Exec=${PROJECT_DIR}/deploy/start-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF
chown -R "${RUN_USER}:${RUN_USER}" "${USER_HOME}/.config" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 6. Autologin la desktop (fără raspi-config manual)
# ---------------------------------------------------------------------------
echo "==> [6/7] Activare autologin desktop pentru '${RUN_USER}'..."
sudo systemctl set-default graphical.target || true

if command -v raspi-config >/dev/null 2>&1; then
  # Metoda oficială Raspberry Pi (funcționează pe Bullseye/Bookworm).
  sudo raspi-config nonint do_boot_behaviour B4 || true
else
  # Fallback LightDM.
  if [ -f /etc/lightdm/lightdm.conf ]; then
    if grep -q "^\[Seat:\*\]" /etc/lightdm/lightdm.conf; then
      if grep -q "autologin-user=" /etc/lightdm/lightdm.conf; then
        sudo sed -i "s/^#\?autologin-user=.*/autologin-user=${RUN_USER}/" /etc/lightdm/lightdm.conf
      else
        sudo sed -i "/^\[Seat:\*\]/a autologin-user=${RUN_USER}" /etc/lightdm/lightdm.conf
      fi
    else
      printf "\n[Seat:*]\nautologin-user=%s\n" "${RUN_USER}" | sudo tee -a /etc/lightdm/lightdm.conf >/dev/null
    fi
  else
    echo "    ATENȚIE: nici raspi-config, nici lightdm.conf găsite."
    echo "    Setează autologin manual dacă afișajul nu pornește la boot."
  fi
fi

# ---------------------------------------------------------------------------
# 7. Verificare
# ---------------------------------------------------------------------------
echo "==> [7/7] Verificare backend..."
sleep 3
if curl -sf "${BACKEND_URL}/api/status" >/dev/null; then
  echo "    Backend OK -> ${BACKEND_URL}/api/status"
else
  echo "    ATENȚIE: backend-ul nu a răspuns încă. Verifică: journalctl -u timer-caspar-backend -f"
fi

echo
echo "======================================================================"
echo " Instalare completă!"
echo
echo " Autologin la desktop: configurat automat."
echo
echo " Ultimul pas — repornește Pi-ul:"
echo "     sudo reboot"
echo
echo " După reboot, afișajul pornește singur fullscreen (fără login manual)."
echo " În casparcg.config (stația de play) adaugă un predefined-client OSC"
echo " către IP-ul acestui Pi, port 7250."
echo "======================================================================"
