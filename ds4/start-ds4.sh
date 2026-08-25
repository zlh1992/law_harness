#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

DS4_DIR="${DS4_DIR:-$HOME/src/ds4}"
MODEL="${DS4_MODEL_PATH:-$DS4_DIR/ds4flash.gguf}"
HOST="${DS4_HOST:-127.0.0.1}"
PORT="${DS4_PORT:-8000}"
CTX="${DS4_CTX:-100000}"
KV_DIR="${DS4_KV_DIR:-$HOME/Library/Caches/ds4-kv}"
KV_SPACE="${DS4_KV_SPACE_MB:-8192}"

[[ -x "$DS4_DIR/ds4-server" ]] || { echo "找不到 $DS4_DIR/ds4-server，请先运行 install/install-ds4-mac.sh。" >&2; exit 2; }
[[ -e "$MODEL" ]] || { echo "找不到模型 $MODEL。" >&2; exit 2; }
mkdir -p "$KV_DIR"
echo "DS4 listening on http://${HOST}:${PORT} (loopback only)"
exec "$DS4_DIR/ds4-server" -m "$MODEL" \
  --ctx "$CTX" \
  --kv-disk-dir "$KV_DIR" \
  --kv-disk-space-mb "$KV_SPACE" \
  --host "$HOST" \
  --port "$PORT"

