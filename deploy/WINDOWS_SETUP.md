# Instalare pe Windows

Pentru rularea afișajului Timer CasparCG pe un PC Windows (de ex. chiar stația
de play). Backend-ul FastAPI ascultă OSC pe UDP 7250, servește build-ul React și
deschide afișajul fullscreen în Edge/Chrome kiosk.

## Cerințe
- Windows 10/11 cu `winget` (App Installer) și `curl` (incluse implicit).
- PowerShell rulat **ca Administrator**.

## Pași

### 1. Copiază proiectul
Pune folderul proiectului oriunde, ex. `C:\timer-caspar` (cu `backend\`,
`frontend\`, `deploy\`).

### 2. Rulează instalatorul (o singură comandă)
Deschide **PowerShell ca Administrator**, apoi:
```powershell
cd C:\timer-caspar
powershell -ExecutionPolicy Bypass -File deploy\install.ps1
```
Scriptul:
1. Instalează Python 3 + Node LTS + yarn (dacă lipsesc, via winget)
2. Creează venv-ul backend + instalează dependențele
3. Buildează frontend-ul (servit de backend pe `localhost:8001`)
4. Deschide portul OSC UDP 7250 în firewall
5. Adaugă autostart în folderul Startup (kiosk la fiecare login)

### 3. Pornește acum (fără restart)
```
deploy\start-timer.bat
```
Se deschide afișajul fullscreen. Ieșire din kiosk: `Alt+F4`.

### 4. Conectează CasparCG
În `casparcg.config` (același PC sau altul din rețea) adaugă:
```xml
<osc>
  <predefined-clients>
    <predefined-client>
      <address>IP_PC_WINDOWS</address>
      <port>7250</port>
    </predefined-client>
  </predefined-clients>
</osc>
```
Dacă CasparCG rulează chiar pe acest PC, poți folosi `127.0.0.1`.

## Verificări
| Ce | Comandă |
|---|---|
| Status backend | `curl http://localhost:8001/api/status` |
| Oprire backend | închide fereastra „timer-backend" sau `taskkill /IM python.exe /F` |

## Note
- MongoDB nu e necesar (neutilizat încă); backend-ul pornește fără el.
- Autostart-ul rulează la **login-ul utilizatorului**. Pentru login automat la
  boot, activează autologin în Windows (`netplwiz` → debifează „Users must enter
  a user name and password").
