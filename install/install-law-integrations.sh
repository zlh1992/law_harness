#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "需要 Python 3.10+。" >&2; exit 2; }

if [[ ! -x "$ROOT_DIR/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT_DIR/.venv"
fi

"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install \
  'numpy>=2.0.2' 'scipy>=1.13.1' 'networkx>=2.8.0' 'python-dateutil>=2.8.0' 'rdflib>=6.2.0' \
  'pypdf>=5.0.0' 'python-docx>=1.1.0' 'openpyxl>=3.1.0' 'python-pptx>=1.0.0'

echo "Semantica、SQLite Memory MCP 与会话文件解析运行时已就绪。"
