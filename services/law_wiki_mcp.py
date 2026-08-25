#!/usr/bin/env python3
"""Read-only MCP facade for the local legal OKF bundle.

The legacy ``search``, ``read_page``, and ``catalog`` tools intentionally stay
available while new callers use the ``okf_*`` contract. No tool mutates the
bundle: curation and approval belong to a separate, reviewed admin workflow.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

try:  # Works both as ``python services/law_wiki_mcp.py`` and package import.
    from okf_law_core import LegalOkfBundle, OkfError, clamp
except ModuleNotFoundError:  # pragma: no cover - used by unit-test package imports.
    from services.okf_law_core import LegalOkfBundle, OkfError, clamp


ROOT = Path(__file__).resolve().parents[1]
WIKI_ROOT = Path(os.environ.get("LAW_WIKI_ROOT", ROOT / "knowledge" / "legal_okf")).resolve()
SERVER_VERSION = "2.0.0"
RESOURCE_PREFIX = "lawwiki://legal-okf/concepts/"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}


def bundle() -> LegalOkfBundle:
    return LegalOkfBundle(WIKI_ROOT)


def _legacy_page(bundle_view: LegalOkfBundle, requested: Any) -> dict[str, Any]:
    path = str(requested or "").strip().replace("\\", "/").lstrip("/")
    if not path:
        raise OkfError("path is required")
    if not path.endswith(".md"):
        path = f"{path}.md"
    document = bundle_view.documents.get(path)
    if document is None:
        raise OkfError("path must identify an existing Markdown page inside the legal OKF bundle")
    content = document["raw"]
    rendered = content[:24_000]
    return {
        "path": document["path"],
        "title": document["title"],
        "content": rendered,
        "truncated": len(content) > len(rendered),
        "characters": len(content),
        "concept_id": document["id"] if not document["reserved"] else None,
        "local_only": True,
    }


def legacy_search(args: dict[str, Any]) -> dict[str, Any]:
    view = bundle()
    found = view.search(str(args.get("query") or ""), limit=clamp(args.get("limit"), 1, 10, 6))
    results = []
    for item in found["results"]:
        results.append({
            "path": item["path"], "title": item["title"], "score": item["score"],
            "line_start": item["line_start"], "line_end": item["line_end"], "snippet": item["snippet"],
            "concept_id": item["id"], "trust": item["trust"],
        })
    return {"query": found["query"], "results": results, "count": len(results), "document_count": len(view.documents), "local_only": True}


def legacy_read_page(args: dict[str, Any]) -> dict[str, Any]:
    return _legacy_page(bundle(), args.get("path"))


def legacy_catalog(_: dict[str, Any]) -> dict[str, Any]:
    view = bundle()
    pages = [
        {"path": document["path"], "title": document["title"], "concept_id": document["id"] if not document["reserved"] else None}
        for document in view.documents.values()
    ]
    return {"pages": pages, "count": len(pages), "okf_version": view.status()["okf_version"], "local_only": True}


def _filters(args: dict[str, Any]) -> dict[str, Any]:
    return {key: args[key] for key in ("type", "status", "trust", "tags", "jurisdiction") if key in args}


def okf_status(_: dict[str, Any]) -> dict[str, Any]:
    return bundle().status()


def okf_list_concepts(args: dict[str, Any]) -> dict[str, Any]:
    concepts = bundle().list_concepts(_filters(args))[:clamp(args.get("limit"), 1, 100, 50)]
    return {"concepts": concepts, "count": len(concepts), "local_only": True}


def okf_search(args: dict[str, Any]) -> dict[str, Any]:
    return bundle().search(str(args.get("query") or ""), limit=clamp(args.get("limit"), 1, 20, 8), filters=_filters(args))


def okf_read_concept(args: dict[str, Any]) -> dict[str, Any]:
    return bundle().get(
        str(args.get("concept_id") or args.get("id") or ""),
        section=str(args.get("section") or ""),
        offset=clamp(args.get("offset"), 0, 100_000, 0),
        limit=clamp(args.get("limit"), 1, 2_000, 1_200),
    )


def okf_graph(_: dict[str, Any]) -> dict[str, Any]:
    return bundle().graph()


def okf_validate(_: dict[str, Any]) -> dict[str, Any]:
    return bundle().validate()


def okf_trace_context(args: dict[str, Any]) -> dict[str, Any]:
    return bundle().trace_context(str(args.get("concept_id") or args.get("id") or ""))


OPERATIONS = {
    "search": legacy_search,
    "read_page": legacy_read_page,
    "catalog": legacy_catalog,
    "okf_status": okf_status,
    "okf_list_concepts": okf_list_concepts,
    "okf_search": okf_search,
    "okf_read_concept": okf_read_concept,
    "okf_graph": okf_graph,
    "okf_validate": okf_validate,
    "okf_trace_context": okf_trace_context,
}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


FILTER_PROPERTIES = {
    "type": {"type": "string", "description": "精确匹配的 OKF type"},
    "status": {"type": "string", "enum": ["draft", "stable", "deprecated"]},
    "trust": {"type": "string", "enum": ["unverified", "machine-confirmed", "human-reviewed"]},
    "tags": {"type": "array", "items": {"type": "string"}},
    "jurisdiction": {"type": "string", "description": "law.jurisdictions 中的法域代码"},
}


TOOLS = [
    {"name": "search", "description": "兼容旧版：检索本地法务 Wiki。新调用方优先使用 okf_search，并在回答前读取具体概念。", "inputSchema": _schema({"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, ["query"])},
    {"name": "read_page", "description": "兼容旧版：读取 search 返回的本地 Markdown 页面；路径受 OKF 根目录严格限制。", "inputSchema": _schema({"path": {"type": "string"}}, ["path"])},
    {"name": "catalog", "description": "兼容旧版：列出 OKF 包内 Markdown 页面和对应的概念 ID。", "inputSchema": _schema({})},
    {"name": "okf_status", "description": "返回本地法务 OKF 包版本、文档数量和合规校验摘要。", "inputSchema": _schema({})},
    {"name": "okf_list_concepts", "description": "按类型、状态、信任信号、标签或法域列出 OKF 概念。", "inputSchema": _schema({**FILTER_PROPERTIES, "limit": {"type": "integer", "minimum": 1, "maximum": 100}})},
    {"name": "okf_search", "description": "按业务关键词检索 OKF 概念，返回概念 ID、摘要、来源数量、信任信号和命中片段。", "inputSchema": _schema({"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}, **FILTER_PROPERTIES}, ["query"])},
    {"name": "okf_read_concept", "description": "按稳定概念 ID 读取 OKF 概念，可按标题区段和行分页，并返回来源、反向链接与信任元数据。", "inputSchema": _schema({"concept_id": {"type": "string"}, "section": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 2000}}, ["concept_id"])},
    {"name": "okf_graph", "description": "返回只读的 OKF 概念图（类别、标准链接和包内来源关系），不暴露绝对主机路径。", "inputSchema": _schema({})},
    {"name": "okf_validate", "description": "校验 OKF v0.2 最小契约、来源、链接、状态与法务包元数据；不写入任何文件。", "inputSchema": _schema({})},
    {"name": "okf_trace_context", "description": "为一个概念返回回答审计所需的来源、信任、时效、链接与引用边界；不会读取外部网页。", "inputSchema": _schema({"concept_id": {"type": "string"}}, ["concept_id"])},
]


def resources() -> list[dict[str, Any]]:
    view = bundle()
    return [
        {"uri": f"{RESOURCE_PREFIX}{quote(concept_id, safe='/')}", "name": document["title"], "description": document["description"], "mimeType": "text/markdown"}
        for concept_id, document in sorted(view.concepts.items())
    ]


def read_resource(uri: str) -> dict[str, Any]:
    if not uri.startswith(RESOURCE_PREFIX):
        raise OkfError("resource URI is outside the legal OKF namespace")
    parsed = urlparse(uri)
    concept_id = unquote(parsed.path.removeprefix("/concepts/")).strip("/")
    view = bundle()
    result = view.get(concept_id, limit=2_000)
    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": view.concepts[result["id"]]["raw"]}]}


def respond(request_id: Any, result: Any) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False), flush=True)


def error(request_id: Any, code: int, message: str) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}, ensure_ascii=False), flush=True)


def _tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in OPERATIONS:
        raise OkfError(f"unknown tool: {name}")
    result = OPERATIONS[name](arguments)
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "structuredContent": result}


def main() -> None:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params") or {}
            if method == "initialize":
                requested = str(params.get("protocolVersion") or "")
                protocol = requested if requested in SUPPORTED_PROTOCOLS else "2025-11-25"
                respond(request_id, {"protocolVersion": protocol, "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}}, "serverInfo": {"name": "law-wiki-okf-readonly", "version": SERVER_VERSION}, "instructions": "Read-only local legal OKF bundle. Use okf_search then okf_read_concept; source registration is not proof that external content was read."})
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                respond(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                try:
                    respond(request_id, _tool_result(str(params.get("name") or ""), params.get("arguments") or {}))
                except Exception as exc:
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps({"error": str(exc)}, ensure_ascii=False)}], "isError": True})
            elif method == "resources/list":
                respond(request_id, {"resources": resources()})
            elif method == "resources/read":
                try:
                    respond(request_id, read_resource(str(params.get("uri") or "")))
                except Exception as exc:
                    respond(request_id, {"contents": [], "_meta": {"error": str(exc)}})
            elif method == "ping":
                respond(request_id, {})
            elif request_id is not None:
                error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            error(None, -32603, str(exc))


if __name__ == "__main__":
    main()
