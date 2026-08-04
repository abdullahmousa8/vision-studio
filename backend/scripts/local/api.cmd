@echo off
rem ============================================================================
rem  Local API server (uvicorn) launcher. Listens on :8000.
rem  Logs to %BACKEND%\logs\api.log.
rem ============================================================================

set "BACKEND=D:\h\gemini-vision-studio\backend"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
if not exist "%BACKEND%\logs\prom" mkdir "%BACKEND%\logs\prom"
del /q "%BACKEND%\logs\prom\*.db" >nul 2>&1
cd /d "%BACKEND%"
set "PATH=%BACKEND%\.venv\Scripts;C:\Windows\System32;C:\Windows"
set "PROMETHEUS_MULTIPROC_DIR=%BACKEND%\logs\prom"
"%BACKEND%\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "%BACKEND%\logs\api.log" 2>&1
