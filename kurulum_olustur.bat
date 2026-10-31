@echo off
rem TekTikla kurulum dosyasini uretir -> Kurulum klasoru
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call kurulum.bat
".venv\Scripts\python.exe" -m pip install -q -U pyinstaller
".venv\Scripts\python.exe" build_release.py || (echo Derleme basarisiz. & pause & exit /b 1)
pause
