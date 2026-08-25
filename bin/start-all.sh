#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="${1:-$PWD}"
PID_FILE="$ROOT_DIR/.proxy.pid"
LOG_FILE="$ROOT_DIR/proxy.log"

cleanup() {
  if [[ -f "$PID_FILE" ]]; then
    PID="$(cat "$PID_FILE")"
    kill "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

"$ROOT_DIR/bin/start-proxy.sh" >"$LOG_FILE" 2>&1 &
PROXY_PID=$!
echo "$PROXY_PID" > "$PID_FILE"
sleep 1
if ! kill -0 "$PROXY_PID" 2>/dev/null; then
  cat "$LOG_FILE" >&2
  exit 1
fi
echo "Proxy started on :4010 (pid $PROXY_PID). Harness logs follow; Ctrl-C stops both."
"$ROOT_DIR/bin/start-harness.sh" "$WORKSPACE_DIR"
