@echo off
echo [INFO] Starting the U-LANC client as the SENDER (Offerer)...
call "venv\Scripts\activate.bat"
python client.py send --server https://staphyloplastic-unrounded-karlyn.ngrok-free.dev
pause