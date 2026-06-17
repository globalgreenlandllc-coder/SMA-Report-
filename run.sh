#!/usr/bin/env bash
# Start SMA-Report locally: Flask backend (:8000) + Vite UI (:5173) together.
# Usage:  ./run.sh        (Ctrl+C stops both)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${PORT:-8000}"
UI_PORT=5173

echo "▸ SMA-Report launcher"

# --- free the ports if something is already listening ---
for p in "$API_PORT" "$UI_PORT"; do
  pids="$(lsof -ti:"$p" 2>/dev/null || true)"
  [ -n "$pids" ] && { echo "  freeing port $p"; kill $pids 2>/dev/null || true; }
done

# --- python deps (only if Flask is missing) ---
if ! python3 -c "import flask" >/dev/null 2>&1; then
  echo "▸ installing Python deps (flask, flask-cors, reportlab)…"
  python3 -m pip install -q -r requirements.txt
fi

# --- node deps (only if not installed) ---
if [ ! -d web/app/node_modules ]; then
  echo "▸ installing UI deps…"
  (cd web/app && npm install --no-audit --no-fund)
fi

# --- start backend ---
echo "▸ starting API on http://localhost:$API_PORT"
PORT="$API_PORT" python3 web/server.py >/tmp/sma-api.log 2>&1 &
API_PID=$!

# --- stop both on exit ---
cleanup() {
  echo; echo "▸ stopping…"
  kill "$API_PID" 2>/dev/null || true
  [ -n "${UI_PID:-}" ] && kill "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- wait for the API to be healthy ---
for _ in $(seq 1 20); do
  if curl -fsS "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

echo "▸ starting UI  on http://localhost:$UI_PORT"
echo
echo "  ➜  Open  http://localhost:$UI_PORT   (Ctrl+C to stop both)"
echo "     API logs: /tmp/sma-api.log"
echo

# --- run the UI in the foreground; Ctrl+C triggers cleanup ---
(cd web/app && npm run dev) &
UI_PID=$!
wait "$UI_PID"
