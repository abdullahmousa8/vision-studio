@echo off
rem ============================================================================
rem  Local Celery worker launcher.
rem
rem  IMPORTANT: prefork pool hangs on Windows when stdout is redirected (tasks
rem  stay stuck in Redis "unacked"). The threads pool runs tasks concurrently
rem  (concurrency=N) and works reliably under redirection, so jobs from multiple
rem  users/tests no longer serialize behind each other.
rem  Logs to %BACKEND%\logs\worker.log.
rem ============================================================================

set "BACKEND=D:\h\gemini-vision-studio\backend"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
if not exist "%BACKEND%\logs\prom" mkdir "%BACKEND%\logs\prom"
del /q "%BACKEND%\logs\prom\*.db" >nul 2>&1
cd /d "%BACKEND%"
set "PATH=%BACKEND%\.venv\Scripts;C:\Windows\System32;C:\Windows;C:\Program Files\OpenSCAD"
set "PROMETHEUS_MULTIPROC_DIR=%BACKEND%\logs\prom"
"%BACKEND%\.venv\Scripts\celery.exe" -A app.core.celery_app worker --loglevel=info --pool=threads --concurrency=2 --queues=pipeline,dlq,default > "%BACKEND%\logs\worker.log" 2>&1
