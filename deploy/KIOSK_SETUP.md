# Autostart fullscreen kiosk on Raspberry Pi

This guide makes the Timer CasparCG display open automatically, fullscreen, in
Chromium every time the Pi boots. The backend (FastAPI) runs as a service, the
React app is built once and served by that same backend on port `8001`, and
Chromium launches in kiosk mode at login.

> Tested on Raspberry Pi OS (Bookworm/Bullseye) with the desktop (LXDE/labwc).

---

## 0. Copy the project to the Pi

Put the project at `/home/pi/timer-caspar` so you have:

```
/home/pi/timer-caspar/backend
/home/pi/timer-caspar/frontend
/home/pi/timer-caspar/deploy   (this folder)
```

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip chromium-browser x11-xserver-utils curl mongodb   # mongodb optional (unused for now)
# Node.js 18+ for building the frontend:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g yarn
```

## 2. Backend: create a virtualenv and install deps

```bash
cd /home/pi/timer-caspar/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Edit `backend/.env` if your channels/layers/port differ (defaults: OSC 7250,
CH1=1/L10, CH2=2/L10). `MONGO_URL` can stay as the local default even if Mongo
isn't installed — it is not used yet.

## 3. Frontend: build once (served by the backend)

The kiosk talks to the backend on the same box, so build the React app pointing
at localhost:

```bash
cd /home/pi/timer-caspar/frontend
yarn install
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn build
```

This creates `frontend/build`, which the backend auto-detects and serves at
`http://localhost:8001` (WebSocket at `ws://localhost:8001/api/ws`).

## 4. Run the backend as a boot service (systemd)

```bash
sudo cp /home/pi/timer-caspar/deploy/timer-caspar-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now timer-caspar-backend
# check it:
systemctl status timer-caspar-backend
curl -s http://localhost:8001/api/status
```

Adjust `User=` and the paths inside the `.service` file if you didn't use the
`pi` user or the `/home/pi/timer-caspar` path.

## 5. Launch Chromium in kiosk mode at boot

Make the launcher executable:

```bash
chmod +x /home/pi/timer-caspar/deploy/start-kiosk.sh
```

### Option A — desktop autostart (easiest)

Create `~/.config/autostart/timer-kiosk.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Timer CasparCG Kiosk
Exec=/home/pi/timer-caspar/deploy/start-kiosk.sh
X-GNOME-Autostart-enabled=true
```

Make sure the Pi boots to the desktop and logs in automatically:
`sudo raspi-config` → **System Options → Boot / Auto Login → Desktop Autologin**.

### Option B — LXDE autostart file

Add this line to `~/.config/lxsession/LXDE-pi/autostart` (or
`/etc/xdg/lxsession/LXDE-pi/autostart`):

```
@/home/pi/timer-caspar/deploy/start-kiosk.sh
```

## 6. Reboot and verify

```bash
sudo reboot
```

On boot the Pi should show the black display: clock on top, then Time Left CH1
and CH2. The footer shows **"Waiting for CasparCG OSC"** until packets arrive.

## 7. Point CasparCG at the Pi

On the playout station, in `casparcg.config`, add a predefined OSC client to the
Pi's IP on port 7250:

```xml
<osc>
  <default-port>6250</default-port>
  <disable-send-to-amcp-clients>false</disable-send-to-amcp-clients>
  <predefined-clients>
    <predefined-client>
      <address>PI_IP_ADDRESS</address>
      <port>7250</port>
    </predefined-client>
  </predefined-clients>
</osc>
```

Restart CasparCG. When a clip plays on channel 1 or 2 layer 10, the countdowns
go live automatically.

---

### Troubleshooting

- **Footer stuck on "Waiting for CasparCG OSC"**: firewall/network — confirm the
  Pi's UDP 7250 is reachable from the playout station (`sudo ufw allow 7250/udp`
  if ufw is active) and that the IP in `casparcg.config` is correct.
- **Screen goes blank after a while**: the launcher already runs `xset` to
  disable blanking; ensure `x11-xserver-utils` is installed.
- **Chromium not found**: on some images the binary is `chromium` not
  `chromium-browser`; the launcher handles both.
- **Backend logs**: `journalctl -u timer-caspar-backend -f`.
