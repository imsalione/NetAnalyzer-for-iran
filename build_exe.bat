@echo off
REM ==========================================
REM NetAnalyzer - EXE Builder
REM ==========================================

echo.
echo =========================================
echo   NetAnalyzer - Building EXE
echo =========================================
echo.

REM ── Step 0: Kill running instance of the app ──────────────────────
REM The EXE must not be running when PyInstaller tries to replace it.
echo [0/5] Stopping any running instances...
taskkill /F /IM InternetMonitor.exe >nul 2>&1
REM Give Windows a moment to release file locks
timeout /t 2 /nobreak >nul

REM ── Step 0b: Pause OneDrive sync ──────────────────────────────────
REM OneDrive holds file locks while syncing, causing PermissionError.
REM We pause it for the duration of the build and resume it afterward.
set ONEDRIVE_PAUSED=0
tasklist /FI "IMAGENAME eq OneDrive.exe" 2>nul | find /I "OneDrive.exe" >nul
if not errorlevel 1 (
    echo [0/5] Pausing OneDrive sync...
    "%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe" /pause >nul 2>&1
    set ONEDRIVE_PAUSED=1
    timeout /t 2 /nobreak >nul
)

REM ── Step 1: Check Python ───────────────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from python.org
    goto :resume_onedrive_and_exit
)
echo        OK

REM ── Step 2: Check / install PyInstaller ───────────────────────────
echo [2/5] Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo        Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        goto :resume_onedrive_and_exit
    )
)
echo        OK

REM ── Step 3: Clean previous build output ───────────────────────────
echo [3/5] Cleaning previous build artifacts...
if exist "build"  rmdir /s /q "build"  2>nul
if exist "dist"   rmdir /s /q "dist"   2>nul

REM If dist still exists (OneDrive still locking), wait a bit more
if exist "dist\InternetMonitor.exe" (
    echo        Waiting for file lock to release...
    timeout /t 5 /nobreak >nul
    del /F /Q "dist\InternetMonitor.exe" 2>nul
)
echo        OK

REM ── Step 4: Build EXE ─────────────────────────────────────────────
echo [4/5] Building EXE (this may take a few minutes)...
echo.
pyinstaller InternetMonitor.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! See output above for details.
    goto :resume_onedrive_and_exit
)
echo.
echo        Build successful.

REM ── Step 5: Create portable package ───────────────────────────────
echo [5/5] Creating portable package...
set PORTABLE_DIR=InternetMonitor_Portable
if exist "%PORTABLE_DIR%" rmdir /s /q "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%"
copy "dist\InternetMonitor.exe" "%PORTABLE_DIR%\" >nul
copy "README.md"                "%PORTABLE_DIR%\" >nul

REM Create ZIP using PowerShell (built into Windows 10/11)
where powershell >nul 2>&1
if not errorlevel 1 (
    if exist "%PORTABLE_DIR%.zip" del /F /Q "%PORTABLE_DIR%.zip"
    powershell -NoProfile -Command ^
        "Compress-Archive -Path '%PORTABLE_DIR%' -DestinationPath '%PORTABLE_DIR%.zip' -Force"
    if not errorlevel 1 (
        echo        ZIP created: %PORTABLE_DIR%.zip
    )
)

REM ── Resume OneDrive ───────────────────────────────────────────────
:resume_onedrive
if "%ONEDRIVE_PAUSED%"=="1" (
    echo.
    echo Resuming OneDrive sync...
    "%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe" /resume >nul 2>&1
)

echo.
echo =========================================
echo   Done!
echo =========================================
echo.
echo   EXE      : dist\InternetMonitor.exe
echo   Portable : %PORTABLE_DIR%\
if exist "%PORTABLE_DIR%.zip" echo   ZIP      : %PORTABLE_DIR%.zip
echo.
pause
exit /b 0

REM ── Error exit ────────────────────────────────────────────────────
:resume_onedrive_and_exit
if "%ONEDRIVE_PAUSED%"=="1" (
    "%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe" /resume >nul 2>&1
)
pause
exit /b 1
