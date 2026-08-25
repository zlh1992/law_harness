#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "此脚本用于 Mac；Windows 请使用 install-windows.ps1。" >&2
  exit 2
fi
command -v node >/dev/null 2>&1 || { echo "需要 Node.js >=20。" >&2; exit 2; }
command -v npm >/dev/null 2>&1 || { echo "需要 npm。" >&2; exit 2; }
command -v codex >/dev/null 2>&1 || { echo "需要先安装 Codex CLI 并确保 codex 在 PATH。" >&2; exit 2; }

if [[ ! -x "$ROOT_DIR/node_modules/.bin/dsh" || ! -e "$ROOT_DIR/node_modules/@law-harness/dsh-session-files" || ! -e "$ROOT_DIR/node_modules/@law-harness/dsh-law-wiki-graph" ]]; then
  (cd "$ROOT_DIR" && npm ci)
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  TOKEN=""
  PUBLIC_PASSWORD=""
  if command -v openssl >/dev/null 2>&1; then TOKEN="$(openssl rand -hex 24)"; fi
  if command -v openssl >/dev/null 2>&1; then PUBLIC_PASSWORD="$(openssl rand -hex 24)"; fi
  [[ -n "$TOKEN" ]] || TOKEN="dsh-$(date +%s)-change-before-lan"
  [[ -n "$PUBLIC_PASSWORD" ]] || PUBLIC_PASSWORD="law-$(date +%s)-change-before-public"
  sed -e "s/^LAW_PROXY_TOKEN=.*/LAW_PROXY_TOKEN=$TOKEN/" -e "s/^PUBLIC_ACCESS_PASSWORD=.*/PUBLIC_ACCESS_PASSWORD=$PUBLIC_PASSWORD/" "$ROOT_DIR/.env.example" > "$ROOT_DIR/.env"
  chmod 600 "$ROOT_DIR/.env"
fi

# DSH forbids protected launcher variables inside a workspace .env. Migrate
# earlier installs once; the start scripts export the protected name in-memory.
if ! grep -q '^LAW_PROXY_TOKEN=' "$ROOT_DIR/.env" && grep -q '^DSH_PROXY_TOKEN=' "$ROOT_DIR/.env"; then
  sed -i '' 's/^DSH_PROXY_TOKEN=/LAW_PROXY_TOKEN=/' "$ROOT_DIR/.env"
  chmod 600 "$ROOT_DIR/.env"
fi

if ! grep -q '^PUBLIC_ACCESS_PASSWORD=' "$ROOT_DIR/.env"; then
  PUBLIC_PASSWORD="$(openssl rand -hex 24 2>/dev/null || date +%s)"
  printf '\nPUBLIC_ACCESS_PASSWORD=%s\n' "$PUBLIC_PASSWORD" >> "$ROOT_DIR/.env"
  chmod 600 "$ROOT_DIR/.env"
fi

if ! grep -q '^MEMORY_NODE_BIN=' "$ROOT_DIR/.env"; then
  MEMORY_NODE_PATH=""
  for candidate in "$(command -v node)" "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"; do
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
mkdir -p "$ROOT_DIR/.dsh-home" "$ROOT_DIR/.codex-proxy-work"
cp "$ROOT_DIR/config/dsh-settings.yaml" "$ROOT_DIR/.dsh-home/settings.yaml"
printf 'DSH_PROXY_TOKEN: %s\n' "$LAW_PROXY_TOKEN" > "$ROOT_DIR/.dsh-home/.credentials.yaml"
chmod 600 "$ROOT_DIR/.dsh-home/.credentials.yaml"

if ! codex login status 2>&1 | grep -qi 'Logged in using ChatGPT'; then
  echo "请先执行 codex login，并选择 ChatGPT 订阅登录。" >&2
  exit 2
fi

echo "安装/初始化完成：$ROOT_DIR"
echo "代理：$ROOT_DIR/bin/start-proxy.sh"
echo "Harness：$ROOT_DIR/bin/start-harness.sh <workspace>"
echo "Token 已写入 .env 和 .dsh-home/.credentials.yaml（请勿提交到 Git）。"
