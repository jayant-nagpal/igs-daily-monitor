@echo off
setlocal
REM ============================================================================
REM install_scheduler.bat - register a Windows Task Scheduler job that runs
REM run_once.bat every 30 minutes, so latest.json stays fresh.
REM
REM Note on market hours: this runs around the clock every 30 minutes. Outside
REM NSE trading hours (09:15-15:30 IST) the sources simply return the last known
REM values, so off-hours runs are harmless. Tighten the window later in Task
REM Scheduler if you prefer.
REM
REM Run this from an Administrator command prompt.
REM ============================================================================

set "ROOT=%~dp0..\.."
set "RUN_ONCE=%~dp0run_once.bat"
set "TASK=IGS Daily Monitor"

if not exist "%RUN_ONCE%" (
  echo [scheduler] run_once.bat not found next to this script.
  exit /b 1
)

echo [scheduler] registering task "%TASK%" (every 30 minutes) ...
schtasks /create /tn "%TASK%" /tr "cmd /c \"%RUN_ONCE%\"" /sc minute /mo 30 /f
if errorlevel 1 (
  echo [scheduler] FAILED - run this from an Administrator command prompt.
  exit /b 1
)

echo [scheduler] installed. Remove it with scripts\windows\uninstall_scheduler.bat
endlocal
