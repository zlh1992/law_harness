#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="$ROOT_DIR"
OPEN_FRONTEND="${RESTART_OPEN_BROWSER:-1}"
FOREGROUND="${RESTART_FOREGROUND:-0}"

usage() {
  cat <<'USAGE'
Usage: ./bin/restart-all.sh [--foreground] [--no-open] [--workspace PATH]

Restarts the local DS4F API and every DeepSeek Harness process running from
this project. Existing chat history is preserved in DSH_HOME.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-open)
      OPEN_FRONTEND=0
      shift
      ;;
    --foreground)
      FOREGROUND=1
      shift
      ;;
    --workspace)
      [[ $# -ge 2 ]] || { echo "--workspace requires a path." >&2; exit 2; }
      WORKSPACE_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -d "$WORKSPACE_DIR" ]] || { echo "Workspace does not exist: $WORKSPACE_DIR" >&2; exit 2; }

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

HARNESS_HOST_VALUE="${HARNESS_HOST:-127.0.0.1}"
HARNESS_PORT_VALUE="${HARNESS_PORT:-3080}"
DS4_HOST_VALUE="${DS4_HOST:-127.0.0.1}"
DS4_PORT_VALUE="${DS4_PORT:-8000}"
DSH_HOME_DIR="${DSH_HOME:-$ROOT_DIR/.dsh-home}"
DS4_START_TIMEOUT="${DS4_START_TIMEOUT_SECONDS:-600}"
HARNESS_START_TIMEOUT="${HARNESS_START_TIMEOUT_SECONDS:-120}"
HARNESS_STOP_TIMEOUT="${HARNESS_STOP_TIMEOUT_SECONDS:-120}"
DS4_STOP_TIMEOUT="${DS4_STOP_TIMEOUT_SECONDS:-60}"
RUN_DIR="$ROOT_DIR/.data/run"
LOG_DIR="$ROOT_DIR/.logs"
DS4_PID_FILE="$RUN_DIR/ds4.pid"
HARNESS_PID_FILE="$RUN_DIR/harness.pid"
DS4_LOG="$LOG_DIR/ds4.log"
HARNESS_LOG="$LOG_DIR/harness.log"

[[ "$HARNESS_HOST_VALUE" == "127.0.0.1" ]] || { echo "HARNESS_HOST must remain 127.0.0.1." >&2; exit 2; }
[[ "$DS4_HOST_VALUE" == "127.0.0.1" ]] || { echo "DS4_HOST must remain 127.0.0.1." >&2; exit 2; }
[[ "$DS4_PORT_VALUE" == "8000" ]] || { echo "This Harness configuration requires DS4_PORT=8000." >&2; exit 2; }
[[ "$OPEN_FRONTEND" =~ ^[01]$ ]] || { echo "RESTART_OPEN_BROWSER must be 0 or 1." >&2; exit 2; }
[[ "$FOREGROUND" =~ ^[01]$ ]] || { echo "RESTART_FOREGROUND must be 0 or 1." >&2; exit 2; }
[[ "$DS4_START_TIMEOUT" =~ ^[0-9]+$ ]] || { echo "DS4_START_TIMEOUT_SECONDS must be an integer." >&2; exit 2; }
[[ "$HARNESS_START_TIMEOUT" =~ ^[0-9]+$ ]] || { echo "HARNESS_START_TIMEOUT_SECONDS must be an integer." >&2; exit 2; }
[[ "$HARNESS_STOP_TIMEOUT" =~ ^[0-9]+$ ]] || { echo "HARNESS_STOP_TIMEOUT_SECONDS must be an integer." >&2; exit 2; }
[[ "$DS4_STOP_TIMEOUT" =~ ^[0-9]+$ ]] || { echo "DS4_STOP_TIMEOUT_SECONDS must be an integer." >&2; exit 2; }

for command_name in curl lsof nohup ps; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "Missing command: $command_name" >&2; exit 2; }
done

mkdir -p "$RUN_DIR" "$LOG_DIR" "$DSH_HOME_DIR"

process_command() {
  ps -p "$1" -ww -o command= 2>/dev/null || true
}

process_cwd() {
  { lsof -a -p "$1" -d cwd -Fn 2>/dev/null || true; } | sed -n 's/^n//p' | head -n 1
}

stop_pid() {
  local pid="$1"
  local label="$2"
  local timeout="${3:-20}"
  local elapsed=0

  kill -0 "$pid" 2>/dev/null || return 0
  echo "Stopping $label (PID $pid)..."
  kill -TERM "$pid" 2>/dev/null || return 0
  while kill -0 "$pid" 2>/dev/null; do
    if (( elapsed >= timeout )); then
      echo "$label did not stop after $timeout seconds; sending SIGKILL." >&2
      kill -KILL "$pid" 2>/dev/null || true
      break
    fi
    sleep 1
    ((elapsed += 1))
  done
}

stop_recorded_pid() {
  local pid_file="$1"
  local kind="$2"
  local pid command_line

  [[ -f "$pid_file" ]] || return 0
  read -r pid < "$pid_file" || true
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  command_line="$(process_command "$pid")"
  case "$kind" in
    harness)
      if [[ "$command_line" == *"dsh web"* ]] && [[ "$(process_cwd "$pid")" == "$ROOT_DIR" ]]; then
        stop_pid "$pid" "DeepSeek Harness" "$HARNESS_STOP_TIMEOUT"
      fi
      ;;
    ds4)
      if [[ "$command_line" == *"ds4-server"* ]]; then
        stop_pid "$pid" "DS4F" "$DS4_STOP_TIMEOUT"
      fi
      ;;
  esac
}

stop_project_harnesses() {
  local pid command_line cwd
  while read -r pid command_line; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [[ "$command_line" == *"dsh web"* ]] || continue
    cwd="$(process_cwd "$pid")"
    if [[ "$cwd" == "$ROOT_DIR" || "$command_line" == *"$ROOT_DIR/node_modules/.bin/dsh"* ]]; then
      stop_pid "$pid" "DeepSeek Harness" "$HARNESS_STOP_TIMEOUT"
    fi
  done < <(ps -ax -ww -o pid=,command=)
}

stop_ds4_listener() {
  local pid command_line
  for pid in $(lsof -nP -tiTCP:"$DS4_PORT_VALUE" -sTCP:LISTEN 2>/dev/null || true); do
    command_line="$(process_command "$pid")"
    if [[ "$command_line" != *"ds4-server"* ]]; then
      echo "Refusing to stop PID $pid on port $DS4_PORT_VALUE; it is not ds4-server." >&2
      exit 2
    fi
    stop_pid "$pid" "DS4F" "$DS4_STOP_TIMEOUT"
  done
}

wait_for_model() {
  local elapsed=0
  local response
  while (( elapsed < DS4_START_TIMEOUT )); do
    response="$(curl -fsS --max-time 5 "http://127.0.0.1:$DS4_PORT_VALUE/v1/models" 2>/dev/null || true)"
    if [[ "$response" == *'"id":"deepseek-v4-flash"'* ]]; then
      return 0
    fi
    if [[ -f "$DS4_PID_FILE" ]]; then
      local pid
      read -r pid < "$DS4_PID_FILE" || true
      if [[ "$pid" =~ ^[0-9]+$ ]] && ! kill -0 "$pid" 2>/dev/null; then
        return 1
      fi
    fi
    sleep 1
    ((elapsed += 1))
  done
  return 1
}

wait_for_harness() {
  local elapsed=0
  while (( elapsed < HARNESS_START_TIMEOUT )); do
    if curl -fsS --max-time 5 "http://127.0.0.1:$HARNESS_PORT_VALUE/" >/dev/null 2>&1; then
      return 0
    fi
    if [[ -f "$HARNESS_PID_FILE" ]]; then
      local pid
      read -r pid < "$HARNESS_PID_FILE" || true
      if [[ "$pid" =~ ^[0-9]+$ ]] && ! kill -0 "$pid" 2>/dev/null; then
        return 1
      fi
    fi
    sleep 1
    ((elapsed += 1))
  done
  return 1
}

echo "Preserving chat history in: $DSH_HOME_DIR"
stop_recorded_pid "$HARNESS_PID_FILE" harness
stop_project_harnesses
stop_recorded_pid "$DS4_PID_FILE" ds4
stop_ds4_listener

printf '\n[%s] Restarting DS4F\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$DS4_LOG"
nohup "$ROOT_DIR/ds4/start-ds4.sh" >> "$DS4_LOG" 2>&1 < /dev/null &
DS4_PID=$!
printf '%s\n' "$DS4_PID" > "$DS4_PID_FILE"
echo "Starting DS4F (PID $DS4_PID); waiting for the model catalog..."
if ! wait_for_model; then
  echo "DS4F failed to become ready. Recent log output:" >&2
  tail -n 40 "$DS4_LOG" >&2
  exit 1
fi

printf '\n[%s] Restarting DeepSeek Harness\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$HARNESS_LOG"
nohup "$ROOT_DIR/bin/start-harness.sh" "$WORKSPACE_DIR" >> "$HARNESS_LOG" 2>&1 < /dev/null &
HARNESS_PID=$!
printf '%s\n' "$HARNESS_PID" > "$HARNESS_PID_FILE"
echo "Starting DeepSeek Harness (PID $HARNESS_PID); waiting for the frontend..."
if ! wait_for_harness; then
  echo "Harness failed to become ready. Recent log output:" >&2
  tail -n 60 "$HARNESS_LOG" >&2
  exit 1
fi

FRONTEND_URL="http://127.0.0.1:$HARNESS_PORT_VALUE/"
echo "Ready:"
echo "  Frontend: $FRONTEND_URL"
echo "  Model API: http://127.0.0.1:$DS4_PORT_VALUE/v1"
echo "  Chat history: $DSH_HOME_DIR"
echo "  Logs: $LOG_DIR"

if [[ "$OPEN_FRONTEND" == "1" ]]; then
  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$FRONTEND_URL" >/dev/null 2>&1 &
  fi
fi

if [[ "$FOREGROUND" == "1" ]]; then
  cleanup_children() {
    trap - EXIT INT TERM
    stop_pid "$HARNESS_PID" "DeepSeek Harness" "$HARNESS_STOP_TIMEOUT"
    stop_pid "$DS4_PID" "DS4F" "$DS4_STOP_TIMEOUT"
  }
  trap cleanup_children EXIT INT TERM
  echo "Supervisor active; press Ctrl-C to stop Harness and DS4F."
  while kill -0 "$HARNESS_PID" 2>/dev/null && kill -0 "$DS4_PID" 2>/dev/null; do
    sleep 5
  done
  echo "A managed service exited unexpectedly." >&2
  exit 1
fi
