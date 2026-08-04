# Native Windows monitoring + edge (no Docker)

Runs Prometheus, Grafana and Traefik as **native Windows binaries** so the whole
Week-11/12 production stack can be demonstrated on a Windows 11 Home machine that
has no Docker and no admin rights.

## Binaries (downloaded once)

| Tool      | Location                                                        |
|-----------|-----------------------------------------------------------------|
| Prometheus | `C:\Users\<you>\devtools\prometheus-<ver>\prometheus.exe`       |
| Grafana    | `C:\Users\<you>\devtools\grafana-<ver>\bin\grafana-server.exe`  |
| Traefik    | `C:\Users\<you>\devtools\traefik.exe`                           |

## Start / stop

```powershell
# Prometheus (:9090) + Grafana (:3000, admin/admin)
.\monitoring\native\run-monitoring.ps1
.\monitoring\native\stop-monitoring.ps1

# Traefik edge (:80 -> :443 HTTPS, self-signed cert, dashboard on :8090)
.\monitoring\native\run-traefik.ps1
.\monitoring\native\stop-traefik.ps1

# Make the browser accept https://localhost (Current User root, no admin)
.\monitoring\native\trust-cert.ps1
```

The self-signed cert (`traefik\certs\localhost.{crt,key}`) is generated locally
and gitignored; regenerate it before the first `run-traefik.ps1`:

```powershell
# (git-bash/MSYS: prefix with MSYS_NO_PATHCONV=1 to avoid path mangling)
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" `
  -addext "subjectAltName=DNS:localhost" `
  -keyout monitoring\native\traefik\certs\localhost.key `
  -out monitoring\native\traefik\certs\localhost.crt
```

PIDs are recorded in `monitoring\native\.pids.json` / `.traefik-pid.json`.
Logs: `backend\logs\prometheus.*.log`, `backend\logs\grafana.*.log`,
`backend\logs\traefik*.log`.

## Verified production flow (single origin)

1. `run-traefik.ps1` terminates TLS at `https://localhost` with a self-signed
   cert (`traefik\certs\localhost.{crt,key}`) and proxies to the API on :8000.
2. The API serves the built SPA from `frontend\dist` (see `backend/app/main.py`
   `SPA_ENABLED`) so browser and API share one HTTPS origin.
3. The 3D viewer fetches the STL through the API, **not** straight from MinIO:

   ```
   GET /api/v1/jobs/{job_id}/artifact/{kind}     kind = model | preview
   ```

   - Requires the user's `Authorization: Bearer` token (401 otherwise).
   - Streams `jobs/{job_id}/output/{model.stl,preview.png}` from MinIO with the
     correct media type (`model/stl`, `image/png`).
   - This exists because presigned MinIO URLs (`http://localhost:9000/...`) are
     **blocked as mixed content** from an HTTPS page; the artifact endpoint keeps
     everything same-origin.

## Grafana on an already-running instance

Provisioning (`grafana\provisioning`) applies on a fresh Grafana start. If Grafana
was already running (e.g. a leftover process you cannot kill without admin
rights), add the data source and dashboard over its HTTP API:

```powershell
$h = @{ Authorization = "Basic $([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:admin')))" }
# 1. data source
$body = @{ name="Prometheus"; type="prometheus"; access="proxy";
           url="http://localhost:9090"; isDefault=$true } | ConvertTo-Json
Invoke-RestMethod -Method Post "http://localhost:3000/api/datasources" -Headers $h -ContentType "application/json" -Body $body
# 2. dashboard (uid = Grafana instance uid; always POST with overwrite=$true)
$dash = Get-Content "monitoring\grafana\dashboards\studio-overview.json" -Raw | ConvertFrom-Json
Invoke-RestMethod -Method Post "http://localhost:3000/api/dashboards/db" -Headers $h -ContentType "application/json" `
  -Body (@{ dashboard = $dash; overwrite = $true } | ConvertTo-Json -Depth 12)
```

## Gotchas learned

- **Duplicate listeners on :8000.** Two `uvicorn` processes can both bind the
  same port on Windows (`SO_REUSEADDR`); connections are split arbitrarily, so
  `/register` and `/login` appear to hit different state. Fix: keep exactly one
  API process (kill the rest, restart via `scripts\local\api.cmd`).
- **`Set-Content` appends a trailing CRLF.** A form body written that way makes
  `password` contain `\r\n`, so `/auth/login` returns 401 even with the right
  password. Write the body without a trailing newline
  (`[IO.File]::WriteAllText`) or use `curl --data-urlencode`.
- **`Get-ChildItem -Path 'prometheus-*' -Filter 'prometheus.exe'`** applies the
  filter to directory names. Use `-Directory` first, then join the path.
- **MSYS/git-bash path mangling**: `-CN=localhost` becomes `C:/Program Files/Git/CN=...`.
  Prefix OpenSSL/curl paths with `MSYS_NO_PATHCONV=1`.
- **Grafana stuck on :3000** (`taskkill /F` = Access denied without admin): use
  the HTTP API above instead of killing it, or reboot.
