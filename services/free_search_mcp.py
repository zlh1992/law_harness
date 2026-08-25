#!/usr/bin/env python3
"""Restricted model-facing facade over the local free-search-mcp package.

The weighted internet research router owns discovery (`search`/`research`).
This facade intentionally exposes only safe follow-up reading tools and never
advertises free-search-mcp's local-file download capability.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

try:  # Supports both `python services/free_search_mcp.py` and package tests.
    from mcp_utils import AsyncRunner, clamp, clean_query, sanitize_error, validate_public_http_url
except ModuleNotFoundError:  # pragma: no cover - exercised by the direct entrypoint above.
    from services.mcp_utils import AsyncRunner, clamp, clean_query, sanitize_error, validate_public_http_url


MAX_BATCH_URLS = 5
MAX_DOCUMENT_CHARS = 200_000
ASYNC_OPERATION_TIMEOUT_SECONDS = 90
_async_runner: AsyncRunner | None = None


def _server():
    try:
        from search_mcp import server
    except ImportError as exc:
        raise RuntimeError("free-search-mcp is not installed; run install/install-internet-tools.sh") from exc
    return server


def _run_async(value: Any) -> Any:
    global _async_runner
    if _async_runner is None:
        _async_runner = AsyncRunner("free-search-mcp")
    return _async_runner.run(value, timeout_seconds=ASYNC_OPERATION_TIMEOUT_SECONDS)


def _format(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def _fetch(args: dict[str, Any]) -> Any:
    url = validate_public_http_url(args.get("url"))
    result = _run_async(_server().fetch(
        url=url,
        render=args.get("render") if args.get("render") in {"auto", "http", "browser"} else "auto",
        force_refresh=bool(args.get("force_refresh", False)),
        max_age_hours=min(max(float(args.get("max_age_hours", 168)), 0), 168) if args.get("max_age_hours") is not None else None,
        inline=False,
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


def _fetch_batch(args: dict[str, Any]) -> Any:
    supplied = args.get("urls")
    if not isinstance(supplied, list) or not supplied:
        raise ValueError("urls must be a non-empty list")
    if len(supplied) > MAX_BATCH_URLS:
        raise ValueError(f"fetch_batch accepts at most {MAX_BATCH_URLS} URLs")
    urls = [validate_public_http_url(value) for value in supplied]
    result = _run_async(_server().fetch_batch(
        urls=urls,
        render=args.get("render") if args.get("render") in {"auto", "http", "browser"} else "auto",
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


def _read_doc(args: dict[str, Any]) -> Any:
    source = validate_public_http_url(args.get("source"))
    start = clamp(args.get("start"), 0, 2_000_000, 0)
    supplied_length = args.get("length")
    if supplied_length is None:
        length = MAX_DOCUMENT_CHARS
    else:
        length = clamp(supplied_length, 0, MAX_DOCUMENT_CHARS, MAX_DOCUMENT_CHARS)
    result = _run_async(_server().read_doc(
        source=source,
        start=start,
        length=length,
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


def _cache_search(args: dict[str, Any]) -> Any:
    result = _run_async(_server().cache_search(
        query=clean_query(args.get("query")),
        limit=clamp(args.get("limit"), 1, 10, 5),
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


def _compare(args: dict[str, Any]) -> Any:
    supplied = args.get("urls")
    if not isinstance(supplied, list) or not 2 <= len(supplied) <= 5:
        raise ValueError("compare requires 2 to 5 URLs")
    result = _run_async(_server().compare(
        question=clean_query(args.get("question")),
        urls=[validate_public_http_url(value) for value in supplied],
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


def _extract_structured(args: dict[str, Any]) -> Any:
    result = _run_async(_server().extract_structured(
        url=validate_public_http_url(args.get("url")),
        format=args.get("format") if args.get("format") in {"markdown", "json"} else "markdown",
    ))
    return _format(result)


TOOLS = [
    {
        "name": "fetch",
        "description": "读取一个已知公开网页。网页搜索必须使用 mcp__internet_research__simple_search 或 deep_research；不接受内网、本机或带凭据的 URL。",
        "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "render": {"enum": ["auto", "http", "browser"]}, "force_refresh": {"type": "boolean"}, "max_age_hours": {"type": "number"}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "fetch_batch",
        "description": "并发读取 2–5 个已知公开网页；每个 URL 的失败会单独返回。",
        "inputSchema": {"type": "object", "required": ["urls"], "properties": {"urls": {"type": "array", "minItems": 1, "maxItems": MAX_BATCH_URLS, "items": {"type": "string"}}, "render": {"enum": ["auto", "http", "browser"]}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "read_doc",
        "description": "读取公开 HTTP(S) PDF、DOCX 或其他文档。只支持远程 URL；本地文件读取已禁用。",
        "inputSchema": {"type": "object", "required": ["source"], "properties": {"source": {"type": "string"}, "start": {"type": "integer", "minimum": 0}, "length": {"type": "integer", "minimum": 0, "maximum": MAX_DOCUMENT_CHARS}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "cache_search",
        "description": "只检索本机 Free Search 缓存中的既有网页正文，不联网。",
        "inputSchema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "compare",
        "description": "针对一个问题并排比较 2–5 个公开 URL。",
        "inputSchema": {"type": "object", "required": ["question", "urls"], "properties": {"question": {"type": "string"}, "urls": {"type": "array", "minItems": 2, "maxItems": 5, "items": {"type": "string"}}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "extract_structured",
        "description": "从一个公开网页提取 JSON-LD、OpenGraph 与 microdata；不用于常规全文阅读。",
        "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "format": {"enum": ["markdown", "json"]}}},
    },
    {
        "name": "engines",
        "description": "列出本机 Free Search 已知搜索引擎；仅供诊断，不能绕过混合搜索路由。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

OPERATIONS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "fetch": _fetch,
    "fetch_batch": _fetch_batch,
    "read_doc": _read_doc,
    "cache_search": _cache_search,
    "compare": _compare,
    "extract_structured": _extract_structured,
    "engines": lambda _: _format(_server().engines()),
}


def respond(request_id: Any, result: Any) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False, default=str), flush=True)


def main() -> None:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params") or {}
            if method == "initialize":
                respond(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "law-harness-free-search", "version": "1.0.0"}})
            elif method == "tools/list":
                respond(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                try:
                    name = params.get("name")
                    if name not in OPERATIONS:
                        raise ValueError(f"tool is unavailable: {name}")
                    result = OPERATIONS[name](params.get("arguments") or {})
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}]})
                except Exception as exc:
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps({"error": sanitize_error(exc), "type": type(exc).__name__}, ensure_ascii=False)}], "isError": True})
            elif method == "ping":
                respond(request_id, {})
            elif request_id is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": sanitize_error(exc)}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
