@echo off
setlocal
set "APP_DIR=%~dp0Backend\original"

if exist "%APP_DIR%\.venv\Scripts\python.exe" (
  "%APP_DIR%\.venv\Scripts\python.exe" "%APP_DIR%\ui_engine_final.py"
  exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%APP_DIR%\ui_engine_final.py"
  exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
  python "%APP_DIR%\ui_engine_final.py"
  exit /b %errorlevel%
)

echo VoiceOS could not find a Python runtime.
echo Add Python to PATH or create Backend\original\.venv, then run this file again.
pause
exit /b 1
