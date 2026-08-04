@echo off
rem ============================================================================
rem  Local PostgreSQL launcher (Windows).
rem
rem  NOTE: launch this via scripts/local/Start-All.ps1 so the postmaster is
rem  created by the WMI provider and survives the parent session. Running it
rem  from a job-object-bound shell may cause backends to die with 0xC0000142.
rem
rem  Requires a pre-initialized data directory (initdb) and a clean environment
rem  (no inherited LANG/LC_ALL/PG*). Logging goes through the logging collector
rem  into %PG_DATA%\log\postgresql.log.
rem ============================================================================

set "PG_BIN=C:\Users\abdul\devtools\postgres\pg\pgsql\bin"
set "PG_DATA=C:\Users\abdul\devtools\postgres\data"

set "PATH=%PG_BIN%;C:\Windows\System32;C:\Windows"
set "TEMP=%TEMP%"
set "TMP=%TMP%"
set "LANG="
set "LC_ALL="

"%PG_BIN%\pg_ctl.exe" -D "%PG_DATA%" -o "-p 5432 -c logging_collector=on -c log_directory=log -c log_filename=postgresql.log" -w start > NUL 2>&1
