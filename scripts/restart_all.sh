#!/usr/bin/env bash
# 重启 IKnow 前后端 + Worker
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Stopping existing processes..."
for port in 8000 5173; do
  for pid in $(lsof -ti :"$port" 2>/dev/null || true); do
    kill "$pid" 2>/dev/null || true
  done
done
pkill -f "${ROOT}/backend/.venv/bin/python -m app.main" 2>/dev/null || true
pkill -f "${ROOT}/backend/.venv/bin/python -m app.worker.scan_loop" 2>/dev/null || true
sleep 1

cd "${ROOT}/backend"
VENV="${ROOT}/backend/.venv/bin/python"
mkdir -p logs

echo "Running init_db migrations..."
"${VENV}" -m app.init_db 2>/dev/null || true

echo "Starting API..."
nohup "${VENV}" -m app.main >>logs/backend.log 2>&1 &
API_PID=$!

echo "Starting scan worker..."
nohup "${VENV}" -m app.worker.scan_loop >>logs/worker.log 2>&1 &
WORKER_PID=$!

cd "${ROOT}/frontend"
if [ ! -d node_modules ]; then
  npm install --silent
fi
nohup npm run dev >>../backend/logs/frontend.log 2>&1 &
WEB_PID=$!

sleep 3
if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  echo "OK  API      http://127.0.0.1:8000  (pid ${API_PID})"
else
  echo "FAIL API did not start — check backend/logs/backend.log"
fi
echo "OK  Worker   pid ${WORKER_PID}  (log: backend/logs/worker.log)"
echo "OK  Frontend http://127.0.0.1:5173  (pid ${WEB_PID})"
