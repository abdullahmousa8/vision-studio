@echo off
rem ============================================================================
rem  Local Celery beat (scheduler) launcher.
rem  On Windows --beat cannot run inside the worker, so it runs as its own
rem  service. Drives periodic tasks such as infra metric reporting.
rem  Logs to %BACKEND%\logs\beat.log.
rem ============================================================================

set "BACKEND=D:\h\gemini-vision-studio\backend"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
cd /d "%BACKEND%"
set "PATH=%BACKEND%\.venv\Scripts;C:\Windows\System32;C:\Windows"
set "PROMETHEUS_MULTIPROC_DIR=%BACKEND%\logs\prom"
"%BACKEND%\.venv\Scripts\celery.exe" -A app.core.celery_app beat --loglevel=info > "%BACKEND%\logs\beat.log" 2>&1
