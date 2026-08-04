# Stop native Traefik started by run-traefik.ps1.
$pidFile = Join-Path $PSScriptRoot ".traefik-pid.json"
if (Test-Path $pidFile) {
  $p = Get-Content $pidFile -Raw | ConvertFrom-Json
  Stop-Process -Id $p.Pid -Force -ErrorAction SilentlyContinue
  Remove-Item $pidFile -Force
  Write-Host "stopped traefik (pid $($p.Pid))"
} else {
  Write-Host "no traefik pid file — nothing to stop"
}
