@echo off
:: This script activates the virtual environment and runs the main Python application.

echo [INFO] Activating virtual environment...
call "venv\Scripts\activate.bat"

echo [INFO] Starting the U-LANC application...
python ulanc_poc.py

echo [INFO] Application closed.
pause