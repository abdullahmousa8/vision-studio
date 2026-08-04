# ============================================================================
#  Local stack status — listening ports + API health check.
#  Usage:  powershell -ExecutionPolicy Bypass -File scripts/local/Status.ps1
# ============================================================================

$ports = @(5432, 6379, 9000, 9001, 8000, 11434)
$labels = @{ 5432 = 'PostgreSQL'; 6379 = 'Redis'; 9000 = 'MinIO API'; 9001 = 'MinIO Console'; 8000 = 'API'; 11434 = 'Ollama' }

Write-Host '--- Listening ports ---'
foreach ($p in $ports) {
    $state = if (Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue) { 'UP' } else { 'down' }
    $color = if ($state -eq 'UP') { 'Green' } else { 'DarkGray' }
    Write-Host ("{0,-6} :{1,-6} {2}" -f $labels[$p], $p, $state) -ForegroundColor $color
}

Write-Host ''
Write-Host '--- Backend health ---'
try {
    $h = Invoke-RestMethod -Uri 'http://localhost:8000/health/' -TimeoutSec 20
    $h.checks.PSObject.Properties | ForEach-Object {
        $c = if ($_.Value -eq 'ok') { 'Green' } else { 'Red' }
        Write-Host ("{0,-8} {1}" -f $_.Name, $_.Value) -ForegroundColor $c
    }
} catch {
    Write-Host "health endpoint unreachable: $($_.Exception.Message)" -ForegroundColor Red
}
