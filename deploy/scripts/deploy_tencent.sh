#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> IKnow Tencent Cloud Deploy"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from example — please edit secrets before production use."
fi

# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" -q
.venv/bin/python -m app.init_db

# Frontend
cd "$ROOT/frontend"
npm install --silent
npm run build

# Docker (optional full stack)
if command -v docker &>/dev/null; then
  cd "$ROOT/deploy"
  docker compose -f docker-compose.prod.yml up -d --build
  echo "Docker stack started on port 80 (frontend) and 8000 (api)"
else
  echo "Docker not found. Install systemd units manually:"
  echo "  sudo cp deploy/systemd/*.service /etc/systemd/system/"
  echo "  sudo systemctl enable iknow-api iknow-worker"
fi

echo "==> Deploy complete"
