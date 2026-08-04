# ============================================================================
#  Local stack orchestrator — stop everything.
#  Stops PostgreSQL gracefully (fast shutdown), then kills Redis, MinIO, API
#  and the Celery worker. It never matches its own PowerShell PID.
# ============================================================================

$ErrorActionPreference = 'Continue'
$ScriptDir  = $PSScriptRoot
$BackendDir = Split-Path -Parent $ScriptDir

# PostgreSQL: graceful shutdown first (safe for crash recovery state).
$pgBin  = 'C:\Users\abdul\devtools\postgres\pg\pgsql\bin'
$pgData = 'C:\Users\abdul\devtools\postgres\data'
if (Test-Path (Join-Path $pgBin 'pg_ctl.exe')) {
    $env:PATH = "$pgBin;C:\Windows\System32;C:\Windows"
    & "$pgBin\pg_ctl.exe" -D $pgData -m fast -w stop 2>$null
    Write-Host 'Stopped PostgreSQL' -ForegroundColor Green
}

# Everything else: terminate matching processes, never $PID.
$matchNames = @('redis-server', 'minio', 'ollama', 'celery', 'uvicorn')
foreach ($p in Get-Process -ErrorAction SilentlyContinue) {
    if ($p.Id -eq $PID) { continue }
    $name = $p.ProcessName
    if ($matchNames -contains $name) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped $name (pid $($p.Id))" -ForegroundColor Green
    }
}

# Any celery/uvicorn that renamed itself (dash -> console_scripts style).
foreach ($p in Get-Process -ErrorAction SilentlyContinue) {
    if ($p.Id -eq $PID) { continue }
    if ($p.ProcessName -match 'python') {
        try { $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine } catch { $cl = '' }
        if ($cl -match 'celery|uvicorn') {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped python worker (pid $($p.Id))" -ForegroundColor Green
        }
    }
}

Write-Host 'Stop complete.'
