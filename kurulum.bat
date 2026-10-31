@echo off
cd /d "%~dp0"
echo TekTikla kuruluyor...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || (echo Python bulunamadi. https://www.python.org adresinden kurun. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -U -r requirements.txt || (echo Kurulum basarisiz. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kisayol.ps1"
echo.
echo Kurulum tamam! Masaustundeki TekTikla kisayoluyla baslatabilirsiniz.
pause
