@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" call kurulum.bat
start "" ".venv\Scripts\pythonw.exe" tektikla.py
