# Timer CasparCG — instalare automată pe Windows (PowerShell)
#
# Rulează O SINGURĂ comandă (PowerShell ca Administrator), din rădăcina proiectului:
#
#     powershell -ExecutionPolicy Bypass -File deploy\install.ps1
#
# Instalează Python + Node, configurează backend-ul, buildează frontend-ul,
# creează scriptul de pornire kiosk și îl adaugă la autostart (folderul Startup).

$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$BackendUrl = "http://localhost:8001"

Write-Host "==> Proiect : $ProjectDir"
Write-Host "==> URL app : $BackendUrl"
Write-Host ""

function Test-Cmd($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# 1. Pachete (Python + Node) via winget
# ---------------------------------------------------------------------------
Write-Host "==> [1/5] Verificare Python / Node..."
if (-not (Test-Cmd "python")) {
  Write-Host "    Instalare Python 3..."
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Test-Cmd "node")) {
  Write-Host "    Instalare Node.js LTS..."
  winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Test-Cmd "yarn")) {
  Write-Host "    Instalare yarn..."
  npm install -g yarn
}

# ---------------------------------------------------------------------------
# 2. Backend: virtualenv + dependențe
# ---------------------------------------------------------------------------
Write-Host "==> [2/5] Configurare backend (venv + pip)..."
Set-Location "$ProjectDir\backend"
if (-not (Test-Path "venv")) {
  python -m venv venv
}
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
if (Test-Path "requirements-run.txt") {
  & ".\venv\Scripts\pip.exe" install -r requirements-run.txt
} else {
  & ".\venv\Scripts\pip.exe" install -r requirements.txt
}

if (-not (Test-Path ".env")) {
@"
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
"@ | Set-Content -Encoding ASCII ".env"
}

# ---------------------------------------------------------------------------
# 3. Frontend: build servit de backend
# ---------------------------------------------------------------------------
Write-Host "==> [3/5] Build frontend React..."
Set-Location "$ProjectDir\frontend"
"REACT_APP_BACKEND_URL=$BackendUrl" | Set-Content -Encoding ASCII ".env"
yarn install
yarn build

# ---------------------------------------------------------------------------
# 4. Firewall: deschide portul OSC 7250 (UDP)
# ---------------------------------------------------------------------------
Write-Host "==> [4/5] Regula firewall pentru OSC UDP 7250..."
try {
  New-NetFirewallRule -DisplayName "Timer CasparCG OSC 7250" `
    -Direction Inbound -Protocol UDP -LocalPort 7250 -Action Allow -ErrorAction Stop | Out-Null
} catch {
  Write-Host "    (regula există deja sau nu am putut-o crea; ignor)"
}

# ---------------------------------------------------------------------------
# 5. Autostart: shortcut catre start-timer.bat in folderul Startup
# ---------------------------------------------------------------------------
Write-Host "==> [5/5] Configurare autostart (kiosk la login)..."
$StartupDir = [Environment]::GetFolderPath("Startup")
$Shortcut   = Join-Path $StartupDir "TimerCasparCG.lnk"
$Target     = Join-Path $ProjectDir "deploy\start-timer.bat"

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($Shortcut)
$sc.TargetPath       = $Target
$sc.WorkingDirectory = Join-Path $ProjectDir "deploy"
$sc.WindowStyle      = 7   # minimized
$sc.Save()

Write-Host ""
Write-Host "======================================================================"
Write-Host " Instalare completa!"
Write-Host ""
Write-Host " Pornire ACUM (fara restart):"
Write-Host "     deploy\start-timer.bat"
Write-Host ""
Write-Host " Autostart: configurat (ruleaza automat la fiecare login Windows)."
Write-Host ""
Write-Host " In casparcg.config adauga un predefined-client OSC catre IP-ul"
Write-Host " acestui PC, port 7250."
Write-Host "======================================================================"
