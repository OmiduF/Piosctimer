@echo off
REM Timer CasparCG - porneste DOAR backend-ul intr-o fereastra VIZIBILA.
REM Foloseste asta ca sa vezi eventualele erori. Ctrl+C pentru oprire.
setlocal enableextensions
set "ROOT=%~dp0.."

echo === Pornire backend Timer CasparCG ===
echo Folder backend: %ROOT%\backend
echo.

if not exist "%ROOT%\backend\venv\Scripts\python.exe" (
  echo [EROARE] Nu gasesc venv-ul: %ROOT%\backend\venv\Scripts\python.exe
  echo Ruleaza din nou install.ps1.
  pause
  exit /b 1
)

cd /d "%ROOT%\backend"
"%ROOT%\backend\venv\Scripts\python.exe" -m uvicorn server:app --host 0.0.0.0 --port 8001

echo.
echo === Backend-ul s-a oprit ===
pause
