@echo off
REM Double-click this file to set up (first run only) and launch the
REM Sponsorship Explorer dashboard. Requires Python 3.10+ already installed
REM (python.org/downloads — check "Add python.exe to PATH" during install).
cd /d "%~dp0"

if not exist ".venv" (
  echo First-time setup: creating a virtual environment and installing dependencies...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

echo Starting the dashboard — once it says "You can now view your Streamlit app",
echo open http://localhost:8501 in your browser.
echo First launch also downloads ~270MB of data; this is a one-time step.
streamlit run app.py
pause
