@echo off
REM ============================================================================
REM  Run HEXR Companion straight from the source in this repo.
REM
REM  FOR DEVELOPERS. If you just want to use the app, build or download
REM  HexR-Companion-Setup.exe instead - it needs no Python at all.
REM
REM  First run installs the two libraries the app needs; after that it launches
REM  straight into the app window.
REM ============================================================================
cd /d "%~dp0.."

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Python isn't installed yet. Opening the download page...
    echo  Install it, TICK "Add Python to PATH" during setup,
    echo  then double-click this file again.
    echo.
    start "" https://www.python.org/downloads/
    pause
    exit /b
)

if not exist ".deps_installed" (
    echo First run: installing Bluetooth + keyboard libraries...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  Install failed. Check your internet connection and try again.
        pause
        exit /b
    )
    echo installed> .deps_installed
)

start "" pythonw hexr_tester.py
exit
