@echo off
REM Activate existing Python env and install dependencies for embedding_app
setlocal

REM Adjust this path if your env is elsewhere
set "VENV_DIR=C:\user\public\python_env"

if not exist "%VENV_DIR%\Scripts\activate.bat" (
  echo Could not find activate script at "%VENV_DIR%\Scripts\activate.bat"
  echo Please update VENV_DIR in setup_env.bat.
  exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

REM Ensure pip is present and up to date
python -m pip install --upgrade pip

REM Install project dependencies
pip install -r requirements.txt

REM Optional: add common Tesseract path for this session (edit if needed)
set "PATH=C:\Program Files\Tesseract-OCR;%PATH%"

echo Environment ready. You can now run the CLI from this window.
endlocal
