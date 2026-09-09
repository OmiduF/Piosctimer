@echo off
REM Timer CasparCG - porneste backend-ul si deschide afisajul in kiosk (Windows).
setlocal enableextensions

set "ROOT=%~dp0.."

if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
  echo [EROARE] Nu gasesc venv-ul. Ruleaza intai: powershell -ExecutionPolicy Bypass -File deploy\install.ps1
  pause
  exit /b 1
)

REM --- Porneste backend-ul intr-o fereastra separata care ramane deschisa la eroare ---
start "timer-backend" cmd /k "cd /d "%ROOT%\backend" && "%ROOT%\backend\venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001"

REM --- Asteapta ca backend-ul sa raspunda (max ~30s) ---
set /a tries=0
:waitloop
curl -s http://localhost:8001/api/status >nul 2>&1
if not errorlevel 1 goto ready
set /a tries+=1
if %tries% GEQ 30 (
  echo [EROARE] Backend-ul nu a pornit in 30s. Verifica fereastra "timer-backend" pentru eroare.
  pause
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo Backend OK. Deschid afisajul...

REM --- Deschide browserul in kiosk (Edge, apoi Chrome, apoi default) ---
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "CHROME86=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if exist "%EDGE%" (
  start "" "%EDGE%" --kiosk http://localhost:8001 --edge-kiosk-type=fullscreen --no-first-run --disable-features=Translate
) else if exist "%CHROME%" (
  start "" "%CHROME%" --kiosk --app=http://localhost:8001 --no-first-run --disable-features=Translate
) else if exist "%CHROME86%" (
  start "" "%CHROME86%" --kiosk --app=http://localhost:8001 --no-first-run --disable-features=Translate
) else (
  start "" http://localhost:8001
)

endlocal
