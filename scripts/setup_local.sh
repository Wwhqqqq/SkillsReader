#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cp -n .env.example .env 2>/dev/null || true

cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" -q
.venv/bin/python -m app.init_db
echo "Backend ready."

cd "$ROOT/frontend"
if command -v npm &>/dev/null; then
  npm install --silent
  echo "Frontend deps installed."
fi

echo "Run:"
echo "  Terminal 1: cd backend && .venv/bin/python -m app.main"
echo "  Terminal 2: cd backend && .venv/bin/python -m app.worker.scan_loop"
echo "  Terminal 3: cd frontend && npm run dev"
