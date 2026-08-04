# Trust the local self-signed TLS certificate (no admin needed).
# Installs monitoring\native\traefik\certs\localhost.crt into the Current User
# trusted root store so browsers and schannel clients accept https://localhost
# without a certificate warning. Restart the browser afterwards.

$cert = Join-Path $PSScriptRoot "traefik\certs\localhost.crt"
if (-not (Test-Path $cert)) { Write-Error "cert not found: $cert" }

$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$store.Open("ReadOnly")
$already = $store.Certificates | Where-Object { $_.Subject -match "CN=localhost" }
$store.Close()

if ($already) {
    Write-Host "localhost cert already trusted until $($already[0].NotAfter)"
    exit 0
}

certutil.exe -user -addstore Root $cert
Write-Host "localhost cert trusted. Restart your browser, then open https://localhost"
