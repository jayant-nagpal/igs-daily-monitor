@echo off
setlocal
REM ============================================================================
REM run_once.bat - generate ONE fresh latest.json for the dashboard.
REM This is the command the scheduler calls every 30 minutes.
REM Read-only: no database writes, no email. Requires configured credentials.
REM ============================================================================

set "ROOT=%~dp0..\.."
pushd "%ROOT%" || (echo [run_once] cannot enter repo root & exit /b 1)

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [run_once] .venv not found - run scripts\windows\setup.bat first.
  popd & exit /b 1
)

REM Mode gates. Live sources also need the credentials from your private doc.
set "env=prod"
set "IGS_ENV=prod"
set "IGS_ALLOW_LIVE=1"

set "PUBLIC=%ROOT%\igs-daily-monitor\public\data\latest.json"
set "DIST=%ROOT%\igs-daily-monitor\dist\data\latest.json"

echo [run_once] producing latest.json (read-only; no writes; no email) ...
"%VENV_PY%" -m dashboard_adapter.live_producer --confirm-live --output "%PUBLIC%"
if errorlevel 1 (
  echo [run_once] producer FAILED - check credentials / ODBC driver / network.
  popd & exit /b 1
)

REM Mirror into the built dashboard so the served copy shows the new data too.
if exist "%ROOT%\igs-daily-monitor\dist" (
  if not exist "%ROOT%\igs-daily-monitor\dist\data" mkdir "%ROOT%\igs-daily-monitor\dist\data"
  copy /y "%PUBLIC%" "%DIST%" >nul
)

echo [run_once] OK -> %PUBLIC%
popd
endlocal
