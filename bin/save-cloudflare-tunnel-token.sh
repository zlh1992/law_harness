#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
TOKEN_FILE="${PUBLIC_TUNNEL_TOKEN_FILE:-$ROOT_DIR/.data/cloudflare-tunnel.token}"
if [[ "$TOKEN_FILE" != /* ]]; then TOKEN_FILE="$ROOT_DIR/$TOKEN_FILE"; fi

mkdir -p "$(dirname "$TOKEN_FILE")"
IFS= read -r -s -p "Cloudflare named tunnel token: " TOKEN
printf '\n' >&2
if [[ -z "$TOKEN" ]]; then
  echo "Token cannot be empty." >&2
  exit 2
fi

umask 077
printf '%s' "$TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"
unset TOKEN
echo "Saved tunnel token to $TOKEN_FILE (mode 600)."
