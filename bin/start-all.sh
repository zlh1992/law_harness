#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="${1:-$PWD}"

# Harness calls the loopback DS4F OpenAI-compatible API directly.
exec "$ROOT_DIR/bin/start-harness.sh" "$WORKSPACE_DIR"
