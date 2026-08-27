#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
echo "== Harness =="
curl -fsS "http://127.0.0.1:${HARNESS_PORT:-3080}/" >/dev/null
echo "ok: http://127.0.0.1:${HARNESS_PORT:-3080}"
echo "== Local DS4F models =="
curl -fsS "http://127.0.0.1:8000/v1/models"
echo
