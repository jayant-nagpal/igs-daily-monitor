@echo off
setlocal
REM ============================================================================
REM setup.bat - one-time setup for the IGS Daily Monitor on Windows.
REM   1. creates a Python virtual environment (.venv)
REM   2. installs Python dependencies
REM   3. installs and builds the React dashboard
REM Run once after cloning. Re-run any time requirements or package.json change.
REM ============================================================================

REM Repo root = two levels up from this script (scripts\windows\).
set "ROOT=%~dp0..\.."
pushd "%ROOT%" || (echo [setup] cannot enter repo root & exit /b 1)

echo [setup] creating virtual environment (.venv) ...
python -m venv .venv || (echo [setup] FAILED to create venv - is Python 3.11 on PATH? & popd & exit /b 1)

set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"

echo [setup] upgrading pip ...
"%VENV_PY%" -m pip install --upgrade pip || (echo [setup] pip upgrade failed & popd & exit /b 1)

echo [setup] installing Python dependencies ...
"%VENV_PY%" -m pip install -r requirements.txt || (echo [setup] pip install failed & popd & exit /b 1)

echo [setup] building the dashboard (npm install + npm run build) ...
pushd igs-daily-monitor || (echo [setup] missing igs-daily-monitor & popd & exit /b 1)
call npm install || (echo [setup] npm install failed - is Node.js installed? & popd & popd & exit /b 1)
call npm run build || (echo [setup] npm run build failed & popd & popd & exit /b 1)
popd

echo.
echo [setup] DONE. Next steps:
echo   1. Put your real credentials in place (see config\.env.example and the
echo      private credentials document you were given).
echo   2. scripts\windows\run_once.bat        - generate a fresh latest.json
echo   3. scripts\windows\serve_dashboard.bat  - open the dashboard in a browser
echo   4. scripts\windows\install_scheduler.bat - refresh every 30 minutes
echo.
popd
endlocal
