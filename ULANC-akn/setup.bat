@echo off
:: This script creates a virtual environment and installs dependencies.

echo [INFO] Setting up the U-LANC project environment...

:: 1. Define the virtual environment directory name
set VENV_DIR=venv

:: 2. Check for Python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

:: 3. Create the virtual environment if it doesn't exist
if not exist %VENV_DIR% (
    echo [INFO] Creating virtual environment in '%VENV_DIR%' folder...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Virtual environment already exists.
)

:: 4. Activate the virtual environment and install dependencies
echo [INFO] Installing dependencies from requirements.txt...
call "%VENV_DIR%\Scripts\activate.bat"
pip install -r requirements.txt

echo.
echo [SUCCESS] Setup is complete!
echo To run the program, first activate the environment by running:
echo %VENV_DIR%\Scripts\activate
echo.
echo Then run the Python script:
echo python ulanc_poc.py
echo.
pause