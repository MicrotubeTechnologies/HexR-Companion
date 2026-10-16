@echo off
REM ============================================================================
REM  HEXR Companion - build the installer.  Double-click this file.
REM
REM  Produces exactly one thing to hand out:
REM
REM      Installer\HexR-Companion-Setup.exe
REM
REM  That file is self-contained. The laptop it runs on needs nothing else -
REM  no Python, no developer tools, no Bluetooth driver.
REM
REM  This machine, the one BUILDING it, does need Python and Inno Setup. If
REM  they are missing, this script offers to install them via winget, which
REM  ships with Windows 10 and 11.
REM
REM  Written with goto and subroutines rather than nested if-blocks: cmd
REM  expands variables for an entire block before running any of it, so
REM  "install it, then look for it again" simply does not work inside one.
REM ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Building the HEXR Companion installer

echo.
echo  ======================================================
echo   Building the HEXR Companion installer
echo  ======================================================
echo.

REM --- 1. Python --------------------------------------------------------------
call :find_python
if defined PY goto :have_python

echo  Python is not installed on this machine, and the build needs it.
echo.
where winget >nul 2>&1
if errorlevel 1 goto :python_by_hand
choice /c YN /n /m "  Install Python now? [Y/N] "
if errorlevel 2 goto :abort
winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
echo.
echo  Python is installed. Windows only picks up a new program's PATH in a
echo  fresh window, so this one has to close.
echo.
echo  Double-click BUILD-INSTALLER.bat again to carry on.
goto :fail

:python_by_hand
echo  Install it once from https://python.org - tick "Add Python to PATH"
echo  during setup - then double-click this file again.
start "" https://www.python.org/downloads/
goto :fail

:have_python
echo  [1/5] Installing build tools. First run takes a minute...
%PY% -m pip install --upgrade pip >nul 2>&1
%PY% -m pip install --quiet -r requirements.txt pyinstaller pillow
if errorlevel 1 goto :deps_failed

REM --- 2. Icon and adb ---------------------------------------------------------
REM The icon is regenerated every build, so the shipped icon can never drift
REM from the generator in tools\ - which is the thing anyone would actually edit.
REM adb is Google's, for the APK Sideload screen: the app carries it, so it
REM needs no internet. Downloaded once and checked against a pinned hash.
echo  [2/5] Drawing the app icon and fetching adb...
%PY% tools\make_icon.py
if errorlevel 1 goto :fail
%PY% tools\fetch_adb.py
if errorlevel 1 goto :fail

REM --- 3. The app -------------------------------------------------------------
echo  [3/5] Building the app. This is the slow part, around a minute...
%PY% -m PyInstaller --noconfirm --clean HexR-Companion.spec
if errorlevel 1 goto :app_failed

REM --- 4. Inno Setup ----------------------------------------------------------
call :find_iscc
if defined ISCC goto :have_iscc

echo.
echo  Inno Setup is missing. It is the free tool that wraps the app up into a
echo  setup .exe, and it is only ever needed on this machine.
echo.
where winget >nul 2>&1
if errorlevel 1 goto :inno_by_hand
choice /c YN /n /m "  Install Inno Setup now? [Y/N] "
if errorlevel 2 goto :abort
winget install --id JRSoftware.InnoSetup --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :fail
call :find_iscc
if defined ISCC goto :have_iscc
echo  Inno Setup still cannot be found. Close this window, open a new one and
echo  run this file again - a fresh window will see the new install.
goto :fail

:inno_by_hand
echo  Download it from https://jrsoftware.org/isdl.php, install it, then
echo  double-click this file again.
start "" https://jrsoftware.org/isdl.php
goto :fail

:have_iscc
echo  [4/5] Packaging the installer...
"%ISCC%" /Q "packaging\HexR-Companion.iss"
if errorlevel 1 goto :pack_failed

REM --- 5. Portable copy -------------------------------------------------------
REM Kept out of Installer\ on purpose. That folder is what gets handed to
REM someone, and it should hold one file with one obvious name. The zip is for
REM locked-down machines that cannot run an installer at all.
echo  [5/5] Zipping a portable copy for locked-down machines...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\HexR-Companion\*' -DestinationPath 'dist\HexR-Companion-portable.zip' -Force"

echo.
echo  ======================================================
echo   Done.
echo.
echo   Send people this one file:
echo       Installer\HexR-Companion-Setup.exe
echo.
echo   They double-click it and get a HEXR Companion icon
echo   on their desktop. Nothing else to install.
echo.
echo   dist\HexR-Companion-portable.zip is the no-install
echo   copy, for machines that block installers.
echo  ======================================================
echo.
start "" explorer "%~dp0Installer"
pause
exit /b 0

REM ---------------------------------------------------------------------------
:find_python
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY exit /b 0
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
exit /b 0

:find_iscc
REM The Program Files (x86) path is quoted throughout: the closing bracket in
REM that folder name would otherwise end a for-loop's argument list early.
set "ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
) do if exist %%P set "ISCC=%%~P"
if defined ISCC exit /b 0
where iscc >nul 2>&1
if not errorlevel 1 set "ISCC=iscc"
exit /b 0

REM ---------------------------------------------------------------------------
:deps_failed
echo.
echo  Could not install the build tools. Check your internet connection.
goto :fail

:app_failed
echo.
echo  The app failed to build. The error is above this message.
goto :fail

:pack_failed
echo.
echo  Packaging failed. The error is above this message.
goto :fail

:abort
echo.
echo  Stopped. Nothing was installed.

:fail
echo.
pause
exit /b 1
