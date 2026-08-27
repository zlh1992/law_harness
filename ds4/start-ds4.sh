#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

USER_HOME="${HOME:?HOME is not set}"
if [[ -z "${DS4_DIR:-}" ]]; then
  if [[ -x "$USER_HOME/.ds4/runtime/ds4-server" ]]; then
    DS4_DIR="$USER_HOME/.ds4/runtime"
  else
    DS4_DIR="$USER_HOME/src/ds4"
  fi
fi
MODEL="${DS4_MODEL_PATH:-$DS4_DIR/ds4flash.gguf}"
HOST="${DS4_HOST:-127.0.0.1}"
PORT="${DS4_PORT:-8000}"
CTX="${DS4_CTX:-393216}"
TOKENS="${DS4_TOKENS:-8192}"
BATCHED_SESSIONS="${DS4_BATCHED_SESSIONS:-4}"
if [[ "$DS4_DIR" == "$USER_HOME/.ds4/runtime" ]]; then
  DEFAULT_KV_DIR="$USER_HOME/.ds4/server-kv"
else
  DEFAULT_KV_DIR="$USER_HOME/Library/Caches/ds4-kv"
fi
KV_DIR="${DS4_KV_DIR:-$DEFAULT_KV_DIR}"
KV_SPACE="${DS4_KV_SPACE_MB:-32768}"
if [[ -z "${DS4_BACKEND:-}" ]]; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    DS4_BACKEND="metal"
  else
    DS4_BACKEND="cpu"
  fi
fi

case "$DS4_BACKEND" in
  metal|cuda|cpu) ;;
  *) echo "不支持的 DS4_BACKEND：$DS4_BACKEND" >&2; exit 2 ;;
esac

[[ -x "$DS4_DIR/ds4-server" ]] || { echo "找不到 $DS4_DIR/ds4-server，请先运行 install/install-ds4-mac.sh。" >&2; exit 2; }
[[ -e "$MODEL" ]] || { echo "找不到模型 $MODEL。" >&2; exit 2; }
mkdir -p "$KV_DIR"
echo "DS4 listening on http://${HOST}:${PORT} (loopback only)"
cd "$DS4_DIR"
exec "$DS4_DIR/ds4-server" -m "$MODEL" \
  "--$DS4_BACKEND" \
  --ctx "$CTX" \
  --tokens "$TOKENS" \
  --batched-session "$BATCHED_SESSIONS" \
  --kv-disk-dir "$KV_DIR" \
  --kv-disk-space-mb "$KV_SPACE" \
  --host "$HOST" \
  --port "$PORT"
