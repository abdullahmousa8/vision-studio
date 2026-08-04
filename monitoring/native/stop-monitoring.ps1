# Stop native Prometheus + Grafana started by run-monitoring.ps1.
$pids = Join-Path $PSScriptRoot ".pids.json"
if (Test-Path $pids) {
  $procs = Get-Content $pids -Raw | ConvertFrom-Json
  foreach ($proc in $procs) {
    Stop-Process -Id $proc.Pid -Force -ErrorAction SilentlyContinue
    Write-Host "stopped $($proc.Name) (pid $($proc.Pid))"
  }
  Remove-Item $pids -Force
} else {
  Write-Host "no .pids.json — nothing to stop (or already stopped)"
}
