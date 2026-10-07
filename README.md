# Piosctimer

### Web-based production timer for CasparCG, vMix and live production

Piosctimer is a lightweight web-based timer designed for **live broadcasting, sports production and professional production workflows**.

The application can run on a **Raspberry Pi 4** and provides dedicated interfaces for both **CasparCG** and **vMix** workflows.

It has been tested in a real production environment and is currently running reliably on Raspberry Pi 4.

---

## 🎬 CasparCG

Piosctimer includes a dedicated interface for **CasparCG** production workflows.

The CasparCG interface is available at:

```text
http://<PI-IP>:8001/
```

### Screenshot

![Piosctimer CasparCG](docs/images/caspar-timer.png)

The CasparCG workflow has been tested with the **latest CasparCG version**.

---

## 🎥 vMix

A dedicated vMix interface is also available.

```text
http://<PI-IP>:8001/vmix
```

### Screenshot

![Piosctimer vMix](docs/images/vmix-timer.png)

This interface is designed specifically for use alongside **vMix production workflows**.

---

## 🍓 Raspberry Pi 4

Piosctimer has been tested and validated on:

**Raspberry Pi 4**

The Raspberry Pi can be used as a dedicated production appliance, allowing the timer to run independently from the main production workstation.

Example:

```text
                    Production LAN

                         │
                         │
                 ┌───────▼────────┐
                 │  Raspberry Pi  │
                 │       4        │
                 │   Piosctimer   │
                 └───────┬────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
          CasparCG                 vMix
          Interface              Interface
              /                     /vmix
```

---

## 🚀 Quick Access

Once Piosctimer is running on the Raspberry Pi:

### CasparCG

```text
http://<PI-IP>:8001/
```

### vMix

```text
http://<PI-IP>:8001/vmix
```

Replace `<PI-IP>` with the IP address of your Raspberry Pi.

---

## ✨ Features

- Web-based production timer
- Dedicated CasparCG interface
- Dedicated vMix interface
- Raspberry Pi 4 compatible
- Designed for local production networks
- Suitable for live broadcasting and sports production
- Lightweight and suitable for dedicated hardware
- Separate frontend and backend architecture
- Deployment resources included
- Testing resources included

---

## 🧪 Tested Environment

Piosctimer has been tested in a real production environment on:

- **Raspberry Pi 4**
- **CasparCG**
- **Latest CasparCG version**
- **vMix**

The application has been running reliably in production testing.

---

## 🤖 Development

Piosctimer was developed with assistance from **Emergent**, an AI-assisted development environment.

The project started from a production requirement and was developed into a working application through iterative testing and validation on real production hardware.

---

## 📁 Project Structure

```text
Piosctimer/
├── backend/
├── frontend/
├── deploy/
├── tests/
├── test_reports/
├── docs/
│   └── images/
│       ├── caspar-timer.png
│       └── vmix-timer.png
└── README.md
```

---

## 🤝 Contributions

Issues, suggestions and pull requests are welcome.

If you find a problem or have an idea for an improvement, please open an issue on GitHub.

---

## 📜 License

See the repository for license information.

---

## 👤 Author

**OmiduF**

Built for real-world live production workflows.
