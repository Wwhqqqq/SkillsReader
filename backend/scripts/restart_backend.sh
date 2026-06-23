#!/usr/bin/env bash
# 一键重启 SkillGetter 后端（默认端口 8000）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8000}"
VENV="${ROOT}/.venv/bin/python"
LOG="${ROOT}/logs/backend.log"

mkdir -p "${ROOT}/logs"

echo "Stopping backend on port ${PORT}..."
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti :"${PORT}" 2>/dev/null || true)
  if [ -n "${PIDS}" ]; then
    kill ${PIDS} 2>/dev/null || true
    sleep 1
  fi
fi
pkill -f "${ROOT}/.venv/bin/python -m app.main" 2>/dev/null || true
sleep 1

echo "Starting backend..."
nohup "${VENV}" -m app.main >>"${LOG}" 2>&1 &
NEW_PID=$!
sleep 2

if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
  echo "OK  Backend running (pid ${NEW_PID}) → http://127.0.0.1:${PORT}"
  echo "Log: ${LOG}"
else
  echo "FAIL Backend did not respond on port ${PORT}. Check ${LOG}"
  exit 1
fi
