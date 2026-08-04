# Local Windows stack (backend\scripts\local\)

Bring up the full local infrastructure (PostgreSQL, Redis, MinIO, API, Celery
worker) with two commands, and inspect status. These are **dev-only** helpers for
this Windows machine; the Docker path in `docker-compose.yml` remains the
portable deployment option.

## Prerequisites (already installed on this machine)

| Component  | Location                                            | Ports      |
|------------|-----------------------------------------------------|------------|
| PostgreSQL | `C:\Users\abdul\devtools\postgres\pg\pgsql` (data: `...\postgres\data`) | 5432 |
| Redis      | `C:\Users\abdul\devtools\redis\Redis-8.10.0-Windows-x64-cygwin` | 6379 |
| MinIO      | `C:\Users\abdul\devtools\minio`                    | 9000 / 9001 |
| OpenSCAD   | `C:\Program Files\OpenSCAD`                        | —          |
| Ollama     | `C:\Users\abdul\AppData\Local\Programs\Ollama` (models `qwen2.5-coder:latest`, `gemma4:latest`) | 11434 |
| Python     | `backend\.venv`                                    | —          |

Paths are hardcoded in each `.cmd` launcher; adjust them at the top of the file
if your install differs.

## Usage

```powershell
# start everything (idempotent: stops stale processes first)
powershell -ExecutionPolicy Bypass -File scripts/local/Start-All.ps1

# stop everything
powershell -ExecutionPolicy Bypass -File scripts/local/Stop-All.ps1

# status: ports + backend health checks
powershell -ExecutionPolicy Bypass -File scripts/local/Status.ps1
```

Individual services can be launched alone via their `.cmd` files
(`postgres.cmd`, `redis.cmd`, `minio.cmd`, `api.cmd`, `worker.cmd`).

## How it works

`Start-All.ps1` launches every `.cmd` through the WMI provider
(`Invoke-CimMethod Win32_Process Create`). Processes created that way are
detached from the calling session's Job Object, so they keep running after the
launcher (or the CLI tool invoking it) exits. Stop-All kills them by name.

Logs go to `backend\logs\`:

- `api.log`, `worker.log`, `redis.log`, `minio.log`
- PostgreSQL: the logging collector writes to
  `C:\Users\abdul\devtools\postgres\data\log\postgresql.log`
  (redirecting the postmaster's stdout to a file breaks crash recovery — never
  use `> file` on the postgres launcher).

## Windows / Celery quirks (why these settings)

- **`--pool=solo`** is mandatory for the Celery worker on Windows: the prefork
  pool hangs when stdout is redirected, leaving tasks stuck in Redis `unacked`.
- The worker sets `PATH` to include `C:\Program Files\OpenSCAD` because the
  stock installer does not add it to the system PATH.
- `postgres.cmd` clears `LANG`/`LC_ALL` and uses `> NUL`: an inherited non-empty
  environment or a file redirect causes backends to die with `0xC0000142`.
