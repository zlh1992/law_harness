#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DS4_DIR="${DS4_DIR:-$HOME/src/ds4}"
if [[ "$(uname -s)" != "Darwin" ]]; then echo "此脚本只用于 macOS。" >&2; exit 2; fi
command -v git >/dev/null 2>&1 || { echo "需要 git。" >&2; exit 2; }
command -v make >/dev/null 2>&1 || { echo "需要 Xcode Command Line Tools。运行 xcode-select --install。" >&2; exit 2; }

mkdir -p "$(dirname "$DS4_DIR")"
if [[ ! -d "$DS4_DIR/.git" ]]; then
  git clone https://github.com/antirez/ds4.git "$DS4_DIR"
fi
cd "$DS4_DIR"
./download_model.sh ds4f-q2
make

if [[ ! -f "$ROOT_DIR/.env" ]]; then cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"; chmod 600 "$ROOT_DIR/.env"; fi
echo "DS4 安装完成。模型链接：$DS4_DIR/ds4flash.gguf"
echo "下一步：$ROOT_DIR/ds4/start-ds4.sh"

