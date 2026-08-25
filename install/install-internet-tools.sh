#!/usr/bin/env bash
set -euo pipefail

# Install exact, auditable upstream snapshots into the ignored .tools tree.
# Do not invoke either upstream's broad installer: this Harness owns MCP
# registration and deliberately excludes cookie-backed and write-capable paths.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
UPSTREAMS_DIR="$TOOLS_DIR/upstreams"
FREE_DIR="$UPSTREAMS_DIR/free-search-mcp"
REACH_DIR="$UPSTREAMS_DIR/agent-reach"
FREE_TAG="v0.9.2"
REACH_TAG="v1.5.0"
FREE_SHA256="bb04f2ffb3846168f7892a8f32b4a2d0729f4d20edf87389ee5b99465434404e"
REACH_SHA256="2808b450a86c054424fcc8b2a2a782b56d3edcf00d587403f560b59553a776c5"
FREE_ARCHIVE="$TOOLS_DIR/free-search-mcp-${FREE_TAG}.tar.gz"
REACH_ARCHIVE="$TOOLS_DIR/agent-reach-${REACH_TAG}.tar.gz"
FREE_URL="https://codeload.github.com/sweetcornna/free-search-mcp/tar.gz/refs/tags/${FREE_TAG}"
REACH_URL="https://codeload.github.com/Panniantong/agent-reach/tar.gz/refs/tags/${REACH_TAG}"
PROJECT_PYTHON="$ROOT_DIR/.venv/bin/python"

command -v curl >/dev/null 2>&1 || { echo "需要 curl。" >&2; exit 2; }
command -v shasum >/dev/null 2>&1 || { echo "需要 shasum。" >&2; exit 2; }
command -v tar >/dev/null 2>&1 || { echo "需要 tar。" >&2; exit 2; }
command -v uv >/dev/null 2>&1 || { echo "需要 uv；请先安装 uv。" >&2; exit 2; }
[[ -x "$PROJECT_PYTHON" ]] || { echo "缺少项目 Python 环境：$PROJECT_PYTHON；请先运行 install-law-integrations.sh。" >&2; exit 2; }

mkdir -p "$UPSTREAMS_DIR"

verify_archive() {
  local archive="$1" expected="$2"
  [[ -f "$archive" ]] || return 1
  [[ "$(shasum -a 256 "$archive" | awk '{print $1}')" == "$expected" ]]
}

download_archive() {
  local archive="$1" url="$2" expected="$3"
  if verify_archive "$archive" "$expected"; then
    return
  fi
  local temp_dir
  temp_dir="$(mktemp -d)"
  curl --fail --location --retry 3 --connect-timeout 10 --max-time 180 --output "$temp_dir/source.tar.gz" "$url"
  verify_archive "$temp_dir/source.tar.gz" "$expected" || { echo "上游归档校验失败：$url" >&2; exit 1; }
  mv "$temp_dir/source.tar.gz" "$archive"
  rmdir "$temp_dir" 2>/dev/null || true
}

ensure_source() {
  local destination="$1" archive="$2" prefix="$3"
  if [[ -d "$destination" ]]; then
    [[ -f "$destination/pyproject.toml" ]] || { echo "上游路径不是完整源码：$destination" >&2; exit 1; }
    return
  fi
  local temp_dir extracted
  temp_dir="$(mktemp -d)"
  tar -xzf "$archive" -C "$temp_dir"
  extracted="$temp_dir/$prefix"
  [[ -d "$extracted" && -f "$extracted/pyproject.toml" ]] || { echo "上游归档内容异常：$archive" >&2; exit 1; }
  mv "$extracted" "$destination"
  rmdir "$temp_dir" 2>/dev/null || true
}

download_archive "$FREE_ARCHIVE" "$FREE_URL" "$FREE_SHA256"
download_archive "$REACH_ARCHIVE" "$REACH_URL" "$REACH_SHA256"
ensure_source "$FREE_DIR" "$FREE_ARCHIVE" "free-search-mcp-0.9.2"
ensure_source "$REACH_DIR" "$REACH_ARCHIVE" "agent-reach-1.5.0"

(
  cd "$FREE_DIR"
  uv sync --frozen
  uv run playwright install chromium
  .venv/bin/python -c 'import search_mcp.server; print("free-search-mcp import OK")'
)
(
  cd "$REACH_DIR"
  uv venv --python "$PROJECT_PYTHON" .venv
  uv pip install --python .venv/bin/python -c constraints.txt -e .
  .venv/bin/python -c 'import agent_reach; print("agent-reach import OK")'
)

printf 'Internet tool sources and isolated runtimes are ready under %s\n' "$UPSTREAMS_DIR"
