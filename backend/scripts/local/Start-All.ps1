# ============================================================================
#  Local stack orchestrator — start everything.
#
#  Launches each service .cmd through the WMI provider (Win32_Process.Create)
#  so the processes are detached from the calling session's Job Object and keep
#  running after this script (or the tool that invoked it) exits.
#
#  Usage:  powershell -ExecutionPolicy Bypass -File scripts/local/Start-All.ps1
# ============================================================================

$ErrorActionPreference = 'Stop'
$ScriptDir  = $PSScriptRoot
$BackendDir = Split-Path -Parent $ScriptDir
$LogsDir    = Join-Path $BackendDir 'logs'

if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }

# --- 1. Stop anything stale --------------------------------------------------
& (Join-Path $ScriptDir 'Stop-All.ps1')

# --- 2. Launch each service via WMI -----------------------------------------
function Start-Detached($Name, $ScriptPath) {
    $abs = Join-Path $ScriptDir $ScriptPath
    if (-not (Test-Path $abs)) { throw "Missing launcher: $abs" }
    $cmd = "cmd.exe /c `"$abs`""
    $null = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    Write-Host "Started $Name ($abs)" -ForegroundColor DarkGray
}

Start-Detached 'postgres' 'postgres.cmd'
Start-Detached 'redis'    'redis.cmd'
Start-Detached 'minio'    'minio.cmd'
Start-Detached 'ollama'   'ollama.cmd'
Start-Detached 'api'      'api.cmd'
Start-Detached 'worker'   'worker.cmd'
Start-Detached 'beat'     'beat.cmd'

# --- 3. Wait for ports -------------------------------------------------------
$targets = @(
    @{ Port = 5432; Name = 'PostgreSQL' },
    @{ Port = 6379; Name = 'Redis' },
    @{ Port = 9000; Name = 'MinIO' },
    @{ Port = 11434; Name = 'Ollama' },
    @{ Port = 8000; Name = 'API' }
)
foreach ($t in $targets) {
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) {
        if (Get-NetTCPConnection -State Listen -LocalPort $t.Port -ErrorAction SilentlyContinue) { $ok = $true; break }
        Start-Sleep -Seconds 1
    }
    if ($ok) { Write-Host "OK  $($t.Name) on :$($t.Port)" -ForegroundColor Green }
    else     { Write-Host "WARN $($t.Name) not listening on :$($t.Port) yet" -ForegroundColor Yellow }
}

Write-Host ''
Write-Host 'Local stack launch complete.' -ForegroundColor Cyan
Write-Host 'Check health:  (Invoke-WebRequest http://localhost:8000/health/).Content'
Write-Host 'Logs:          backend\logs\*.log (worker.log, beat.log, api.log, redis.log, minio.log)'
Write-Host 'PostgreSQL:    backend\data-log via logging collector (data\log\postgresql.log)'
