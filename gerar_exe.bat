@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FTECH_Compras --hidden-import win32timezone FTECH_Compras.py
echo EXE: dist\FTECH_Compras.exe
pause
