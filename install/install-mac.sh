#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "此脚本用于 Mac；Windows 请使用 install-windows.ps1。" >&2
  exit 2
fi
if ! command -v node >/dev/null 2>&1; then
  PROJECT_NODE="$ROOT_DIR/.tools/node/bin/node"
  [[ -x "$PROJECT_NODE" ]] || { echo "需要 Node.js >=20。" >&2; exit 2; }
  export PATH="$(dirname "$PROJECT_NODE"):$PATH"
fi

if [[ ! -x "$ROOT_DIR/node_modules/.bin/dsh" || ! -e "$ROOT_DIR/node_modules/@law-harness/dsh-session-files" || ! -e "$ROOT_DIR/node_modules/@law-harness/dsh-law-wiki-graph" ]]; then
  command -v npm >/dev/null 2>&1 || { echo "依赖未安装且 npm 不在 PATH。" >&2; exit 2; }
  (cd "$ROOT_DIR" && npm ci)
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  chmod 600 "$ROOT_DIR/.env"
fi

if ! grep -q '^MEMORY_NODE_BIN=' "$ROOT_DIR/.env"; then
  MEMORY_NODE_PATH=""
  for candidate in "$(command -v node)" "$ROOT_DIR/.tools/node/bin/node"; do
    [[ -x "$candidate" ]] || continue
    major="$($candidate -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
    if [[ "$major" == "22" || "$major" == "23" || "$major" == "24" ]]; then
      MEMORY_NODE_PATH="$candidate"
      break
    fi
  done
  if [[ -n "$MEMORY_NODE_PATH" ]]; then
    printf 'MEMORY_NODE_BIN=%s\n' "$MEMORY_NODE_PATH" >> "$ROOT_DIR/.env"
  else
    printf 'MEMORY_NODE_BIN=\n' >> "$ROOT_DIR/.env"
    echo "提示：请安装 Node.js 22/24 LTS 后再运行 install-law-integrations.sh。" >&2
  fi
  chmod 600 "$ROOT_DIR/.env"
fi

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a
export DS4_API_KEY="${DS4_API_KEY:-local}"
mkdir -p "$ROOT_DIR/.dsh-home"
cp "$ROOT_DIR/config/dsh-settings.yaml" "$ROOT_DIR/.dsh-home/settings.yaml"
printf 'DS4_API_KEY: %s\n' "$DS4_API_KEY" > "$ROOT_DIR/.dsh-home/.credentials.yaml"
chmod 600 "$ROOT_DIR/.dsh-home/.credentials.yaml"

echo "安装/初始化完成：$ROOT_DIR"
echo "Harness：$ROOT_DIR/bin/start-harness.sh <workspace>"
echo "Harness 已固定为本机 DS4F：http://127.0.0.1:8000/v1 / deepseek-v4-flash。"
