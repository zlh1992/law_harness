#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
PORT="${PROXY_PORT:-4010}"
TOKEN="${LAW_PROXY_TOKEN:-${DSH_PROXY_TOKEN:-${PROXY_TOKEN:-}}}"
echo "== proxy health =="
curl -fsS "http://127.0.0.1:${PORT}/healthz"
echo
echo "== models =="
curl -fsS -H "Authorization: Bearer ${TOKEN}" "http://127.0.0.1:${PORT}/v1/models"
echo
