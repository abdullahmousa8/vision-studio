@echo off
rem ============================================================================
rem  Local MinIO launcher (Windows). API on :9000, console on :9001.
rem  Logs to %BACKEND%\logs\minio.log.
rem ============================================================================

set "MINIO_DIR=C:\Users\abdul\devtools\minio"
set "MINIO_DATA=C:\Users\abdul\devtools\minio\data"
set "BACKEND=D:\h\gemini-vision-studio\backend"

set "MINIO_ROOT_USER=minioadmin"
set "MINIO_ROOT_PASSWORD=minioadmin"
rem Public Prometheus metrics (no auth) — reachable only on this host.
set "MINIO_PROMETHEUS_AUTH_TYPE=public"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
cd /d "%MINIO_DIR%"
minio.exe server "%MINIO_DATA%" --address ":9000" --console-address ":9001" > "%BACKEND%\logs\minio.log" 2>&1
