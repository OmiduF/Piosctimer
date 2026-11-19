# Timer CasparCG — macOS

## Instalare (o singură dată)
1. Instalează **Python 3** (https://www.python.org/downloads/macos/) și **Node.js LTS** (https://nodejs.org).
2. În Terminal:
   ```
   cd ~/timer-caspar
   bash deploy/install-mac.sh
   ```

## Pornire
- Dublu-click pe `deploy/start-timer-mac.command` (prima dată: click dreapta → Open, dacă macOS îl blochează).
- Se deschide Chrome fullscreen (dacă e instalat), altfel browserul implicit.
- Ieșire din fullscreen: `Cmd + Q` pe Chrome. Oprire timer: închide fereastra Terminal.

## OnTheAir pe același Mac
În `/settings`, la **IP Mac OnTheAir** pune `127.0.0.1`, apoi porturile HyperDeck ale celor 3 output-uri (ex. 9993 / 9994 / 9995 — exact ce ai setat în OnTheAir).

## Update
```
cd ~/timer-caspar && git fetch origin && git reset --hard origin/main
cd frontend && yarn build
```
