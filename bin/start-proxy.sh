#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

export PROXY_HOST="${PROXY_HOST:-127.0.0.1}"
export PROXY_PORT="${PROXY_PORT:-4010}"
export PROXY_TOKEN="${LAW_PROXY_TOKEN:-${DSH_PROXY_TOKEN:-${PROXY_TOKEN:-}}}"
export CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-sol}"
export MAX_CONCURRENCY="${MAX_CONCURRENCY:-1}"

if [[ -z "$PROXY_TOKEN" || "$PROXY_TOKEN" == "请替换为随机高强度口令" ]]; then
  echo "请先在 $ROOT_DIR/.env 设置 LAW_PROXY_TOKEN。" >&2
  echo "可运行：$ROOT_DIR/install/install-mac.sh" >&2
  exit 2
fi

mkdir -p "${CODEX_BRIDGE_CWD:-$ROOT_DIR/.codex-proxy-work}"

exec node "$ROOT_DIR/bridge/proxy.mjs"
