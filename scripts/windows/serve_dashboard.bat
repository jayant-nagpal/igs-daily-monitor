@echo off
setlocal
REM ============================================================================
REM serve_dashboard.bat - serve the built dashboard on http://localhost:4173
REM The page auto-refreshes latest.json every 30 minutes on its own; keep the
REM scheduler installed so that file actually gets regenerated (see README).
REM Press Ctrl+C to stop.
REM ============================================================================

set "ROOT=%~dp0..\.."
set "DIST=%ROOT%\igs-daily-monitor\dist"
set "VENV_PY=%ROOT%\.venv\Scripts\python.exe"
set "PORT=4173"

if not exist "%DIST%\index.html" (
  echo [serve] dashboard not built yet - run scripts\windows\setup.bat first.
  exit /b 1
)
if not exist "%VENV_PY%" (
  echo [serve] .venv not found - run scripts\windows\setup.bat first.
  exit /b 1
)

echo [serve] serving %DIST%
echo [serve] open http://localhost:%PORT% in your browser
"%VENV_PY%" -m http.server %PORT% --directory "%DIST%"
endlocal
