#!/usr/bin/env bash
set -euo pipefail

# The public gateway belongs to the disabled public-access stack.
echo "Public gateway is disabled in this local-only checkout." >&2
exit 2

: <<'PUBLIC_GATEWAY_DISABLED'
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${PUBLIC_ACCESS_PASSWORD:-}" || "${PUBLIC_ACCESS_PASSWORD:-}" == "请替换为随机高强度口令" ]]; then
  echo "请先在 $ROOT_DIR/.env 设置 PUBLIC_ACCESS_PASSWORD。" >&2
  exit 2
fi

export PUBLIC_GATEWAY_HOST="${PUBLIC_GATEWAY_HOST:-127.0.0.1}"
export PUBLIC_GATEWAY_PORT="${PUBLIC_GATEWAY_PORT:-4180}"
export HARNESS_HOST="${HARNESS_HOST:-127.0.0.1}"
export HARNESS_PORT="${HARNESS_PORT:-3080}"
export LAW_SESSION_FILES_ROOT="${LAW_SESSION_FILES_ROOT:-$ROOT_DIR/workspaces/session-files}"
export PUBLIC_UPLOAD_ROOT="${PUBLIC_UPLOAD_ROOT:-$LAW_SESSION_FILES_ROOT}"

exec node "$ROOT_DIR/gateway/public-gateway.mjs"
PUBLIC_GATEWAY_DISABLED
