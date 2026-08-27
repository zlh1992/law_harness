#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_DIR="${1:-$PWD}"
if [[ ! -d "$WORKSPACE_DIR" ]]; then
  echo "Workspace does not exist: $WORKSPACE_DIR" >&2
  exit 2
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
if [[ -f "$ROOT_DIR/.env.research" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env.research"
  set +a
fi

if ! command -v node >/dev/null 2>&1; then
  NODE_BIN="${MEMORY_NODE_BIN:-$ROOT_DIR/.tools/node/bin/node}"
  [[ -x "$NODE_BIN" ]] || { echo "需要 Node.js >=20。" >&2; exit 2; }
  export PATH="$(dirname "$NODE_BIN"):$PATH"
fi

export DSH_HOME="${DSH_HOME:-$ROOT_DIR/.dsh-home}"
export DS4_API_KEY="${DS4_API_KEY:-local}"
export DS4_MODEL_ID="deepseek-v4-flash"
export LAW_MODEL_ID="$DS4_MODEL_ID"
export LAW_AGENT_PRESETS_DIR="$ROOT_DIR/dsh/presets"
export LAW_PROJECT_SKILLS_DIR="$ROOT_DIR/.dsh/skills"
export LAW_MEMORY_PYTHON="$ROOT_DIR/.venv/bin/python"
export LAW_MEMORY_MCP_ENTRY="$ROOT_DIR/services/local_memory_mcp.py"
export LAW_MEMORY_DB="$ROOT_DIR/.data/memory/memory.db"
export LAW_SESSION_FILES_ROOT="${LAW_SESSION_FILES_ROOT:-$ROOT_DIR/workspaces/session-files}"
export LAW_SESSION_FILE_PYTHON="${LAW_SESSION_FILE_PYTHON:-$ROOT_DIR/.venv/bin/python}"
export LAW_SESSION_FILE_EXTRACTOR="${LAW_SESSION_FILE_EXTRACTOR:-$ROOT_DIR/services/session_file_extract.py}"
export LAW_WIKI_PYTHON="$ROOT_DIR/.venv/bin/python"
export LAW_WIKI_MCP_ENTRY="$ROOT_DIR/services/law_wiki_mcp.py"
export LAW_WIKI_ROOT="$ROOT_DIR/knowledge/legal_okf"
export LAW_FREE_SEARCH_ROOT="$ROOT_DIR/.tools/upstreams/free-search-mcp"
export LAW_FREE_SEARCH_PYTHON="$LAW_FREE_SEARCH_ROOT/.venv/bin/python"
export LAW_FREE_SEARCH_MCP_ENTRY="$ROOT_DIR/services/free_search_mcp.py"
export LAW_FREE_SEARCH_ROUTER_CACHE_PATH="$ROOT_DIR/.data/free-search/router"
export LAW_FREE_SEARCH_READER_CACHE_PATH="$ROOT_DIR/.data/free-search/reader"
export LAW_RESEARCH_PYTHON="$LAW_FREE_SEARCH_PYTHON"
export LAW_RESEARCH_MCP_ENTRY="$ROOT_DIR/services/internet_research_mcp.py"
export LAW_RESEARCH_AUDIT_PATH="$ROOT_DIR/.data/research/search-audit.jsonl"
# Cordis MCP env values must be strings; unset paid-provider keys stay optional.
export TAVILY_API_KEY="${TAVILY_API_KEY:-}"
export EXA_API_KEY="${EXA_API_KEY:-}"
export SERPAPI_API_KEY="${SERPAPI_API_KEY:-}"
export LAW_AGENT_REACH_ROOT="$ROOT_DIR/.tools/upstreams/agent-reach"
export LAW_AGENT_REACH_PYTHON="$LAW_AGENT_REACH_ROOT/.venv/bin/python"
export LAW_AGENT_REACH_MCP_ENTRY="$ROOT_DIR/services/agent_reach_mcp.py"
export LAW_AGENT_REACH_AUDIT_PATH="$ROOT_DIR/.data/research/agent-reach-audit.jsonl"
export LAW_SEMANTICA_PYTHON="$ROOT_DIR/.venv/bin/python"
export LAW_SEMANTICA_MCP_ENTRY="$ROOT_DIR/services/semantica_law_mcp.py"
export LAW_SEMANTICA_SOURCE_PATH="$ROOT_DIR/vendor/semantica"
export LAW_SEMANTICA_GRAPH_PATH="$ROOT_DIR/.data/semantica/context-graph.json"
export LAW_SEMANTICA_PROVENANCE_PATH="$ROOT_DIR/.data/semantica/provenance.sqlite"
export LAW_SEMANTICA_TRACE_PATH="$ROOT_DIR/.data/semantica/legal-traces.json"
export DSH_PERMISSION_MODE="${DSH_PERMISSION_MODE:-read-only}"
export DSH_TELEMETRY_MODE="${DSH_TELEMETRY_MODE:-DISABLED}"
# Local-only deployment: do not allow .env to expose the UI on a LAN/WAN interface.
export HARNESS_HOST="127.0.0.1"
export HARNESS_PORT="${HARNESS_PORT:-3080}"
export DSH_VERSION="${DSH_VERSION:-0.1.0-rc.7}"
DS4_MODELS="$(curl -fsS --max-time 5 "http://127.0.0.1:8000/v1/models" 2>/dev/null || true)"
if [[ "$DS4_MODELS" != *'"id":"deepseek-v4-flash"'* ]]; then
  echo "本地 DS4F 尚未就绪；请确认 http://127.0.0.1:8000/v1/models 可访问。" >&2
  exit 2
fi
if [[ ! -x "$LAW_SEMANTICA_PYTHON" || ! -x "$LAW_MEMORY_PYTHON" || ! -f "$LAW_MEMORY_MCP_ENTRY" || ! -f "$LAW_WIKI_MCP_ENTRY" || ! -f "$LAW_RESEARCH_MCP_ENTRY" || ! -f "$LAW_SESSION_FILE_EXTRACTOR" || ! -d "$LAW_WIKI_ROOT" ]]; then
  echo "缺少法务集成运行时；请先运行：$ROOT_DIR/install/install-law-integrations.sh" >&2
  exit 2
fi
if [[ ! -x "$LAW_FREE_SEARCH_PYTHON" || ! -x "$LAW_AGENT_REACH_PYTHON" || ! -f "$LAW_FREE_SEARCH_MCP_ENTRY" || ! -f "$LAW_AGENT_REACH_MCP_ENTRY" || ! -f "$LAW_FREE_SEARCH_ROOT/pyproject.toml" || ! -f "$LAW_AGENT_REACH_ROOT/pyproject.toml" ]]; then
  echo "缺少本地联网集成运行时；请先运行：$ROOT_DIR/install/install-internet-tools.sh" >&2
  exit 2
fi
mkdir -p "$LAW_FREE_SEARCH_ROUTER_CACHE_PATH" "$LAW_FREE_SEARCH_READER_CACHE_PATH" "$(dirname "$LAW_RESEARCH_AUDIT_PATH")" "$(dirname "$LAW_AGENT_REACH_AUDIT_PATH")"
mkdir -p "$DSH_HOME"
PRESET_SOURCE="$ROOT_DIR/dsh/presets/law-assistant"
PRESET_TARGET_ROOT="$DSH_HOME/.agent-presets"
PRESET_TARGET="$PRESET_TARGET_ROOT/law-assistant"
if [[ ! -d "$PRESET_SOURCE" ]]; then
  echo "缺少法务 Agent 预设：$PRESET_SOURCE" >&2
  exit 2
fi
mkdir -p "$PRESET_TARGET_ROOT"
if [[ -e "$PRESET_TARGET" && ! -d "$PRESET_TARGET" ]]; then
  echo "法务 Agent 预设目标不是目录：$PRESET_TARGET" >&2
  exit 2
fi
if [[ ! -d "$PRESET_TARGET" ]]; then
  cp -R "$PRESET_SOURCE" "$PRESET_TARGET"
else
  # The target is launcher-managed; refresh reviewed preset files on restart.
  cp -R "$PRESET_SOURCE/." "$PRESET_TARGET"
fi

# DSH profiles resolve plugin packages from their own `node_modules` tree.
# Keep the two project-owned plugins linked there so a new DSH_HOME is usable
# without publishing or globally installing either development package.
PROFILE_PLUGIN_ROOT="$DSH_HOME/profiles/web/node_modules/@law-harness"
mkdir -p "$PROFILE_PLUGIN_ROOT"
ensure_profile_plugin_link() {
  local package_name="$1"
  local source="$2"
  local target="$PROFILE_PLUGIN_ROOT/$package_name"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "Harness profile plugin target is not a managed link: $target" >&2
    exit 2
  fi
  if [[ -L "$target" ]]; then
    rm "$target"
  fi
  ln -s "$source" "$target"
}
ensure_profile_plugin_link "dsh-session-files" "$ROOT_DIR/plugins/session-files"
ensure_profile_plugin_link "dsh-law-wiki-graph" "$ROOT_DIR/plugins/law-wiki-graph"

cp "$ROOT_DIR/config/dsh-settings.yaml" "$DSH_HOME/settings.yaml"
cp "$ROOT_DIR/config/dsh-law-cordis.patch.yml" "$DSH_HOME/cordis.patch.yml"
printf 'DS4_API_KEY: %s\n' "$DS4_API_KEY" > "$DSH_HOME/.credentials.yaml"
chmod 600 "$DSH_HOME/.credentials.yaml"

cd "$WORKSPACE_DIR"
if [[ -n "${DSH_BIN:-}" ]]; then
  exec "$DSH_BIN" web --host "$HARNESS_HOST" --port "$HARNESS_PORT"
fi
LOCAL_DSH_BIN="$ROOT_DIR/node_modules/.bin/dsh"
if [[ -x "$LOCAL_DSH_BIN" ]]; then
  exec "$LOCAL_DSH_BIN" web --host "$HARNESS_HOST" --port "$HARNESS_PORT"
fi

exec npx --prefer-offline -y "@deepseek-ai/dsh@$DSH_VERSION" web --host "$HARNESS_HOST" --port "$HARNESS_PORT"
