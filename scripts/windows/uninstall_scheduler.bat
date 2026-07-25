@echo off
setlocal
REM ============================================================================
REM uninstall_scheduler.bat - remove the "IGS Daily Monitor" scheduled task.
REM Run from an Administrator command prompt.
REM ============================================================================

set "TASK=IGS Daily Monitor"

echo [scheduler] removing task "%TASK%" ...
schtasks /delete /tn "%TASK%" /f
if errorlevel 1 (
  echo [scheduler] task not found or removal failed (may already be gone).
  exit /b 1
)

echo [scheduler] removed.
endlocal
