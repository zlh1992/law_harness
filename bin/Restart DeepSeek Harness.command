#!/usr/bin/env bash
set -uo pipefail

# Resolve the repository location even when Finder opens this file through a
# Desktop symlink.
SOURCE_PATH="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE_PATH" ]]; do
  SOURCE_DIR="$(cd -P "$(dirname "$SOURCE_PATH")" && pwd)"
  LINK_TARGET="$(readlink "$SOURCE_PATH")"
  if [[ "$LINK_TARGET" == /* ]]; then
    SOURCE_PATH="$LINK_TARGET"
  else
    SOURCE_PATH="$SOURCE_DIR/$LINK_TARGET"
  fi
done

SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE_PATH")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

clear
printf 'Restarting DeepSeek V4 Flash API, Harness Agent, and frontend...\n\n'

if "$ROOT_DIR/bin/restart-all.sh"; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display notification "API, agent, and frontend are ready." with title "DeepSeek Harness restarted"' >/dev/null 2>&1 || true
  fi
  printf '\nRestart complete. You may close this window.\n'
  exit 0
fi

STATUS=$?
printf '\nRestart failed with status %s. Review the output above and logs in:\n%s/.logs\n' "$STATUS" "$ROOT_DIR" >&2
if command -v osascript >/dev/null 2>&1; then
  osascript -e 'display dialog "DeepSeek Harness restart failed. Review the Terminal output and project logs." with title "Restart failed" buttons {"OK"} default button "OK" with icon stop' >/dev/null 2>&1 || true
fi
exit "$STATUS"
