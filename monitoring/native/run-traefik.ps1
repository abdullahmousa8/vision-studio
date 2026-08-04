# Start Traefik natively on Windows (no Docker) using the configs in this folder.
# Requires the traefik.exe binary at C:\Users\<you>\devtools\traefik.exe
param(
  [string]$TraefikExe = "C:\Users\abdul\devtools\traefik.exe"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $TraefikExe)) { Write-Error "traefik.exe not found at $TraefikExe" }

# Launch fully detached (no inherited stdout/stderr handles) so the caller's
# shell does not wait on Traefik's output pipe. Traefik logs to files
# configured in traefik.yml (log.filePath / accessLog.filePath).
$p = Start-Process -FilePath $TraefikExe `
  -ArgumentList "--configFile=$(Join-Path $PSScriptRoot 'traefik\traefik.yml')" `
  -WindowStyle Hidden `
  -PassThru

@(@{ Name = "traefik"; Pid = $p.Id }) | ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot ".traefik-pid.json")

Start-Sleep -Seconds 4
Write-Host "Traefik up (pid $($p.Id)). https://localhost  | dashboard http://localhost:8090"
Write-Host "Logs: backend\logs\traefik.log"
