@echo off
REM Quick start script for QCAN Explorer (Windows)

echo QCAN Explorer - CAN Network Analysis Tool
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Python version check: OK

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
echo Installing minimal requirements first...
pip install -r requirements-minimal.txt

echo Attempting to install additional packages...
pip install "numpy>=1.21.0" || echo Warning: numpy installation failed, continuing without it
pip install "pandas>=2.2.0" || echo Warning: pandas installation failed, continuing without it
pip install "pyqtgraph>=0.13.0" || echo Warning: pyqtgraph installation failed, continuing without it

REM Run the application
echo Starting QCAN Explorer...
echo.
python main.py

pause
