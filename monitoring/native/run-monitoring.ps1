# Start Prometheus + Grafana natively on Windows (no Docker).
# Requires the binaries downloaded once (see README in this folder):
#   prometheus  -> C:\Users\<you>\devtools\prometheus-<ver>\prometheus.exe
#   grafana     -> C:\Users\<you>\devtools\grafana-<ver>\bin\grafana-server.exe
param(
  [string]$ToolsDir = "C:\Users\abdul\devtools"
)

$ErrorActionPreference = "Stop"
$root = "D:\h\gemini-vision-studio"
$logs = Join-Path $root "backend\logs"
New-Item -ItemType Directory -Force -Path $logs, (Join-Path $logs "grafana-data"), (Join-Path $logs "prometheus-data") | Out-Null

$promDir = Get-ChildItem -Path (Join-Path $ToolsDir "prometheus-*") -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
$prom = if ($promDir) { Get-Item (Join-Path $promDir.FullName "prometheus.exe") -ErrorAction SilentlyContinue } else { $null }
$graf = Get-ChildItem -Path (Join-Path $ToolsDir "grafana-*") -Recurse -Filter "grafana-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $prom) { Write-Error "prometheus.exe not found under $ToolsDir. Download: https://prometheus.io/download/" }
if (-not $graf) { Write-Error "grafana-server.exe not found under $ToolsDir. Download: https://grafana.com/grafana/download" }

# ---- Prometheus ----
$promArgs = @(
  "--config.file=$(Join-Path $root 'monitoring\native\prometheus.yml')",
  "--storage.tsdb.path=$(Join-Path $logs 'prometheus-data')",
  "--web.listen-address=:9090"
)
$p = Start-Process -FilePath $prom.FullName -ArgumentList $promArgs -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "prometheus.out.log") -RedirectStandardError (Join-Path $logs "prometheus.err.log") -PassThru

# ---- Grafana ----
$grafHome = $graf.Directory.Parent.FullName
$env:GF_PATHS_DATA = Join-Path $logs "grafana-data"
$env:GF_PATHS_LOGS = $logs
$env:GF_PATHS_PROVISIONING = Join-Path $root "monitoring\native\grafana\provisioning"
$env:GF_SECURITY_ADMIN_PASSWORD = "admin"
$grafArgs = @(
  "--homepath=$grafHome",
  "--config=$(Join-Path $grafHome 'conf\defaults.ini')",
  "--packaging=zip"
)
$g = Start-Process -FilePath $graf.FullName -ArgumentList $grafArgs -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "grafana.out.log") -RedirectStandardError (Join-Path $logs "grafana.err.log") -PassThru

@(
  @{ Name = "prometheus"; Pid = $p.Id },
  @{ Name = "grafana"; Pid = $g.Id }
) | ConvertTo-Json | Set-Content -Path (Join-Path $root "monitoring\native\.pids.json")

Start-Sleep -Seconds 6
Write-Host "Prometheus : http://localhost:9090  (pid $($p.Id))"
Write-Host "Grafana    : http://localhost:3000  admin/admin (pid $($g.Id))"
Write-Host "Logs: $logs\prometheus.*.log, grafana.*.log"
