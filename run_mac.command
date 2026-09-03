#!/bin/bash
# Double-click this file to set up (first run only) and launch the Sponsorship
# Explorer dashboard. Requires Python 3.10+ already installed
# (python.org/downloads or `brew install python`).
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First-time setup: creating a virtual environment and installing dependencies..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q --upgrade pip
  pip install -q -r requirements.txt
else
  source .venv/bin/activate
fi

echo "Starting the dashboard — once it says 'You can now view your Streamlit app',"
echo "open http://localhost:8501 in your browser (it won't open automatically)."
echo "First launch also downloads ~270MB of data; this is a one-time step."
streamlit run app.py
