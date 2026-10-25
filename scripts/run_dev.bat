@echo off
REM CircuitSleuth dev launcher (Windows): backend :8100 + frontend :5173
cd /d "%~dp0.."
if not exist .venv (
  echo Creating virtualenv...
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
)
if not exist data\demo\scenario_01_clear_defects (
  .venv\Scripts\python.exe tools\generate_dataset.py
)
start "circuitsleuth-api" .venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8100
cd frontend
if not exist node_modules call npm install
start "circuitsleuth-web" cmd /c "npm run dev"
echo Backend: http://127.0.0.1:8100/api/health  UI: http://localhost:5173
