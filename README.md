# Piosctimer

### A lightweight web-based timer for live production, broadcasting and sports events.

Piosctimer is a web-based production timer designed for **live broadcasting, sports production, studio workflows and streaming environments**.

The project started from a simple idea: create a dedicated, reliable timer that can be used in a real production environment without depending on a large or complicated broadcast application.

The application was developed with the assistance of **Emergent**, an AI-powered development environment, and subsequently tested and refined for real-world use.

> **Tested and running successfully on Raspberry Pi 4.**

---

## 🎬 What is Piosctimer?

Piosctimer provides a dedicated timer application that can be deployed on a local network and accessed through a web browser.

The goal is simple:

**Start the application → open it from a browser → use the timer in your production workflow.**

It is particularly useful when a production team needs a dedicated timing tool that can run independently from the main production computer.

---

## 🏟️ Designed for Live Production

Piosctimer was created with real-world broadcast workflows in mind.

Possible use cases include:

- Live sports broadcasts
- TV and streaming productions
- Studio productions
- Match-day production
- Event production
- Countdown workflows
- Production timing
- Remote operator control
- Broadcast graphics workflows

It can be used alongside systems such as **vMix, CasparCG and Bitfocus Companion**, depending on the production workflow.

---

## 🍓 Raspberry Pi

One of the main goals of the project is to make Piosctimer suitable for inexpensive, dedicated hardware.

### Tested hardware

**Raspberry Pi 4**

The application has been installed and tested on a Raspberry Pi 4 and has been found to operate reliably in this environment.

This makes it possible to dedicate a small Raspberry Pi to the timer instead of using a full production workstation.

A typical setup can therefore look like:

```text
                 Production Network

                       ┌──────────────┐
                       │ Piosctimer   │
                       │ Raspberry Pi │
                       │      4       │
                       └──────┬───────┘
                              │
                         Network / LAN
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
          vMix           CasparCG        Companion
             │
             ▼
       Broadcast Output
```

---

## 🧩 Project Structure

The repository is organized into separate application and deployment components:

```text
Piosctimer/
│
├── backend/        Backend application
├── frontend/       Web interface
├── deploy/         Deployment resources
├── tests/          Automated tests
├── test_reports/   Test results
├── memory/         Development/project data
│
├── README.md
└── test_result.md
```

---

## 🚀 Development

Piosctimer was developed with the help of **Emergent**, an AI-assisted development platform.

The project was not intended to be an academic demonstration or a purely experimental application. The development process focused on reaching a practical result that could actually be deployed and used on production hardware.

The application was subsequently tested on a **Raspberry Pi 4** as part of the validation process.

---

## 🧪 Testing

The repository contains dedicated testing resources and test reports.

The application has been tested in a Raspberry Pi 4 environment and is currently considered functional for the intended production use case.

Further testing and improvements are expected as the project evolves.

---

## 🔧 Future Development

Possible future improvements include:

- Additional remote-control options
- More production-oriented controls
- Improved integration with broadcast systems
- Additional API endpoints
- Better integration with Stream Deck / Bitfocus Companion
- Additional Raspberry Pi deployment options
- Improved documentation
- More configurable timer modes

---

## 🤝 Contributions

Suggestions, bug reports and improvements are welcome.

If you find a problem or have an idea for a feature, feel free to open an **Issue** or submit a **Pull Request**.

---

## 📜 License

See the repository for the current license information.

---

## 👤 Project

**Piosctimer**  
Created and maintained by **OmiduF**

GitHub: https://github.com/OmiduF/Piosctimer
