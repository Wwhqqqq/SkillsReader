#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
fi

# Kill existing on ports
for pid in $(lsof -ti:8000 2>/dev/null); do kill "$pid" 2>/dev/null || true; done
for pid in $(lsof -ti:5173 2>/dev/null); do kill "$pid" 2>/dev/null || true; done

cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -e ".[dev]" -q
fi
.venv/bin/python -m app.init_db 2>/dev/null || true

.venv/bin/python -m app.main &
API_PID=$!
.venv/bin/python -m app.worker.scan_loop &
WORKER_PID=$!

cd "$ROOT/frontend"
npm run dev &
WEB_PID=$!

echo "IKnow started:"
echo "  API:      http://127.0.0.1:8000"
echo "  Frontend: http://127.0.0.1:5173"
echo "  PIDs: api=$API_PID worker=$WORKER_PID web=$WEB_PID"
echo "Press Ctrl+C to stop all."

trap "kill $API_PID $WORKER_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
