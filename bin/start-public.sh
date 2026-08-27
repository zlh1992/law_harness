#!/usr/bin/env bash
set -euo pipefail

# This checkout intentionally supports loopback-only access.
echo "Public access is disabled; use ./bin/start-all.sh for 127.0.0.1:3080." >&2
exit 2
