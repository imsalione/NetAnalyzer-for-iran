@echo off
REM ==========================================
REM NetAnalyzer - EXE Builder
REM ==========================================

echo.
echo =========================================
echo   NetAnalyzer - Building EXE
echo =========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

REM Check PyInstaller
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

REM Clean previous builds
echo Cleaning previous build artifacts...
if exist "build"  rmdir /s /q "build"
if exist "dist"   rmdir /s /q "dist"

echo.
echo Building EXE (this may take a few minutes)...
echo.

REM Build using existing spec file for reproducible builds
pyinstaller InternetMonitor.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the output above for details.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   Build Complete!
echo =========================================
echo.
echo EXE: dist\InternetMonitor.exe
echo.

REM Create portable package
set PORTABLE_DIR=InternetMonitor_Portable
if exist "%PORTABLE_DIR%" rmdir /s /q "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%"

copy "dist\InternetMonitor.exe" "%PORTABLE_DIR%\" >nul
copy "README.md"                "%PORTABLE_DIR%\" >nul

echo Portable package: %PORTABLE_DIR%\
echo.

REM Optional: create zip
where powershell >nul 2>&1
if not errorlevel 1 (
    echo Creating zip archive...
    powershell -Command "Compress-Archive -Path '%PORTABLE_DIR%' -DestinationPath '%PORTABLE_DIR%.zip' -Force"
    if not errorlevel 1 (
        echo ZIP: %PORTABLE_DIR%.zip
    )
)

echo.
pause
