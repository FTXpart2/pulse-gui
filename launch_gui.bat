@echo off
REM Double-click launcher for the pulse-gui application.
REM Creates the virtual environment and installs requirements on first run.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo Launching pulse-gui...
".venv\Scripts\python.exe" run_pulse_gui.py

if errorlevel 1 (
    echo.
    echo The GUI exited with an error. See the messages above.
    pause
)
