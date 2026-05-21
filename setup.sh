#!/bin/bash
set -e
echo "Setting up Job Bot..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install chrome
cd ui && npm install && npm run build && cd ..
echo "Setup complete! Run: python launch.py"
