@echo off
echo Setting up Job Bot for Windows...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install chrome
cd ui
npm install
npm run build
cd ..
echo Setup complete! Run: python launch.py
pause
