@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3.10 -m venv .venv
  if not exist .venv (
    echo Instale Python 3.10, 3.11 ou 3.12 de 64 bits e tente novamente.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000
