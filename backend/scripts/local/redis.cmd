@echo off
rem ============================================================================
rem  Local Redis launcher (Windows, redis-windows build).
rem  Logs to %BACKEND%\logs\redis.log.
rem ============================================================================

set "REDIS_DIR=C:\Users\abdul\devtools\redis\Redis-8.10.0-Windows-x64-cygwin"
set "BACKEND=D:\h\gemini-vision-studio\backend"

if not exist "%BACKEND%\logs" mkdir "%BACKEND%\logs"
cd /d "%REDIS_DIR%"
redis-server.exe --port 6379 > "%BACKEND%\logs\redis.log" 2>&1
