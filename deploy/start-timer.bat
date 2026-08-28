@echo off
REM Timer CasparCG - porneste backend-ul si deschide afisajul in kiosk (Windows).
setlocal enableextensions

set "ROOT=%~dp0.."

REM --- Porneste backend-ul (minimizat) ---
pushd "%ROOT%\backend"
start "timer-backend" /min "%ROOT%\backend\venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001
popd

REM --- Asteapta ca backend-ul sa raspunda ---
:waitloop
curl -s http://localhost:8001/api/status >nul 2>&1
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto waitloop
)

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
