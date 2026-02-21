@echo off
REM ==========================================
REM Internet Monitor - Windows Installation
REM ==========================================

echo.
echo =========================================
echo   Internet Monitor - Installation
echo =========================================
echo.

REM Check Python
echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python from: https://python.org
    echo NOTE: Check "Add Python to PATH" during installation
    pause
    exit /b 1
)
echo [OK] Python found

REM Check pip
echo.
echo [2/3] Checking pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not available!
    pause
    exit /b 1
)
echo [OK] pip available

REM Install dependencies
echo.
echo [3/3] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed!
    pause
    exit /b 1
)

echo.
echo =========================================
echo   Installation Complete!
echo =========================================
echo.
echo To run the application:
echo   python main.py
echo.
echo Or double-click: run.bat
echo.

REM Create run.bat
echo @echo off > run.bat
echo python main.py >> run.bat

echo Do you want to run the application now? (Y/N)
set /p RUN_NOW="Your choice: "

if /i "%RUN_NOW%"=="Y" (
    echo.
    echo Starting application...
    python main.py
)

pause
