#!/usr/bin/env python3
"""Small MCP adapter that makes each legal answer auditable with Semantica.

The original Semantica project is vendored in ``vendor/semantica``.  This
adapter intentionally exposes a narrow tool surface: agents may record and
retrieve answer traces, but cannot mutate arbitrary graph data from a public
law-assistant session.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_PATH = Path(
    os.environ.get("SEMANTICA_SOURCE_PATH", Path(__file__).resolve().parents[1] / "vendor" / "semantica")
).resolve()
if str(SOURCE_PATH) not in sys.path:
    sys.path.insert(0, str(SOURCE_PATH))

from semantica.context import ContextGraph  # noqa: E402
from semantica.provenance import ProvenanceManager, compute_checksum  # noqa: E402
from semantica.provenance.schemas import ProvenanceEntry  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = Path(os.environ.get("SEMANTICA_GRAPH_PATH", ROOT / ".data" / "semantica" / "context-graph.json"))
PROVENANCE_PATH = Path(
    os.environ.get("SEMANTICA_PROVENANCE_PATH", ROOT / ".data" / "semantica" / "provenance.sqlite")
)
TRACE_PATH = Path(os.environ.get("SEMANTICA_TRACE_PATH", ROOT / ".data" / "semantica" / "legal-traces.json"))
MODEL_ID = os.environ.get("LAW_MODEL_ID", "deepseek-v4-flash")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: Any, limit: int) -> str:
    rendered = str(value or "").strip()
    return rendered[:limit]


def json_response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def json_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class LegalTraceStore:
    """Persists Semantica decision objects plus W3C PROV-O-compatible records."""

    def __init__(self) -> None:
        for path in (GRAPH_PATH, PROVENANCE_PATH, TRACE_PATH):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.graph = ContextGraph(advanced_analytics=False)
        if GRAPH_PATH.exists():
            try:
                self.graph.load_from_file(str(GRAPH_PATH))
            except Exception as exc:  # A broken audit file must not stop the assistant.
                print(f"Could not load Semantica graph: {exc}", file=sys.stderr)
        self.provenance = ProvenanceManager(storage_path=str(PROVENANCE_PATH))
        self.traces = self._load_traces()

    def _load_traces(self) -> dict[str, dict[str, Any]]:
        if not TRACE_PATH.exists():
            return {}
        try:
            loaded = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Could not load Semantica trace index: {exc}", file=sys.stderr)
            return {}

    def _flush(self) -> None:
        self.graph.save_to_file(str(GRAPH_PATH))
        fd, temporary_path = tempfile.mkstemp(prefix="legal-traces-", suffix=".json", dir=TRACE_PATH.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.traces, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, TRACE_PATH)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @staticmethod
    def _sources(raw_sources: Any) -> list[dict[str, str]]:
        if not isinstance(raw_sources, list):
            return []
        normalised: list[dict[str, str]] = []
        for item in raw_sources[:20]:
            if isinstance(item, str):
                source = text(item, 500)
                if source:
                    normalised.append({"source": source, "title": source, "location": "", "quote": ""})
                continue
            if not isinstance(item, dict):
                continue
            source = text(item.get("source") or item.get("url") or item.get("path"), 500)
            title = text(item.get("title") or source, 300)
            if not source:
                continue
            normalised.append(
                {
                    "source": source,
                    "title": title,
                    "location": text(item.get("location") or item.get("section"), 300),
                    "quote": text(item.get("quote"), 1200),
                }
            )
        return normalised

    def record(self, args: dict[str, Any]) -> dict[str, Any]:
        question = text(args.get("question"), 5000)
        answer = text(args.get("answer"), 20000)
        if not question or not answer:
            raise ValueError("question and answer are required")

        confidence = args.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence must be a number between 0 and 1") from exc
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be a number between 0 and 1")

        sources = self._sources(args.get("sources"))
        skill = text(args.get("skill"), 1000)
        uncertainty = text(args.get("uncertainty"), 2000)
        trace_id = f"lawtrace-{uuid.uuid4().hex[:16]}"
        source_ids: list[str] = []

        with self.lock:
            for item in sources:
                source_id = "law-source-" + hashlib.sha256(
                    f"{item['source']}\0{item['location']}".encode("utf-8")
                ).hexdigest()[:20]
                source_ids.append(source_id)
                self.graph.add_node(
                    source_id,
                    "legal_source",
                    content=item["title"],
                    source=item["source"],
                    location=item["location"],
                )
                self.provenance.track_entity(
                    source_id,
                    source=item["source"],
                    entity_type="legal_source",
                    activity_id="law_source_reference",
                    source_location=item["location"] or None,
                    source_quote=item["quote"] or None,
                    confidence=1.0,
                    metadata={"title": item["title"]},
                )

            decision_id = self.graph.record_decision(
                category="legal_response",
                scenario=question,
                reasoning=(
                    "法务助手依据本地技能/知识库与明确来源生成风险分流回答。"
                    f" 使用技能：{skill or '未声明'}。不确定性：{uncertainty or '未声明'}。"
                ),
                outcome=answer[:1000],
                confidence=confidence,
                entities=source_ids,
                decision_maker=f"law-harness-{MODEL_ID}",
                metadata={
                    "trace_id": trace_id,
                    "skill": skill,
                    "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                    "source_count": len(source_ids),
                },
            )
            for source_id in source_ids:
                self.graph.add_edge(decision_id, source_id, "supported_by", weight=confidence)

            provenance_source = source_ids[0] if source_ids else "user-provided-and-model-synthesis"
            entry = self.provenance.track_entity(
                trace_id,
                source=provenance_source,
                entity_type="legal_answer_trace",
                activity_id="law_harness_answer",
                confidence=confidence,
                source_quote=answer[:2000],
                metadata={
                    "decision_id": decision_id,
                    "question": question,
                    "skill": skill,
                    "uncertainty": uncertainty,
                    "source_ids": source_ids,
                    "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                },
            )
            self.traces[trace_id] = {
                "trace_id": trace_id,
                "decision_id": decision_id,
                "created_at": now(),
                "question": question,
                "answer": answer,
                "skill": skill,
                "uncertainty": uncertainty,
                "confidence": confidence,
                "sources": sources,
                "source_ids": source_ids,
                "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                "provenance_checksum": entry.checksum,
            }
            self._flush()

        return {
            "trace_id": trace_id,
            "decision_id": decision_id,
            "source_count": len(sources),
            "integrity_checksum": entry.checksum,
            "message": "Semantica decision and provenance records persisted locally.",
        }

    def get(self, trace_id: str) -> dict[str, Any]:
        with self.lock:
            trace = self.traces.get(trace_id)
            if not trace:
                raise ValueError("trace_id was not found")
            entry = self.provenance.get_provenance(trace_id)
            # Semantica's manager API returns a serialised dict, while its
            # integrity helper accepts the dataclass. Rehydrate before
            # computing the checksum so trace retrieval works across restarts.
            provenance_entry = ProvenanceEntry.from_dict(entry) if entry else None
            valid = bool(
                provenance_entry
                and entry.get("checksum") == compute_checksum(provenance_entry)
            )
            return {"trace": trace, "provenance": entry, "integrity_verified": valid}

    def search(self, query: str, limit: int) -> dict[str, Any]:
        needle = text(query, 500).lower()
        if not needle:
            raise ValueError("query is required")
        with self.lock:
            results = [
                {
                    "trace_id": item["trace_id"],
                    "created_at": item["created_at"],
                    "question": item["question"],
                    "skill": item["skill"],
                    "confidence": item["confidence"],
                    "source_count": len(item["sources"]),
                }
                for item in reversed(list(self.traces.values()))
                if needle in (item["question"] + "\n" + item["answer"] + "\n" + item["skill"]).lower()
            ][:limit]
        return {"results": results, "count": len(results)}

    def summary(self) -> dict[str, Any]:
        with self.lock:
            return {
                "trace_count": len(self.traces),
                "graph_path": str(GRAPH_PATH),
                "provenance_path": str(PROVENANCE_PATH),
                "trace_path": str(TRACE_PATH),
            }


STORE = LegalTraceStore()

TOOLS = [
    {
        "name": "record_legal_answer",
        "description": "在发送实质性法务回答前记录 Semantica 决策、答案哈希和每个可核验来源。必须提供拟发送的完整答案和来源；不要记录身份证号、完整合同或未脱敏个人信息。",
        "inputSchema": {
            "type": "object",
            "required": ["question", "answer"],
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "skill": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "uncertainty": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "title": {"type": "string"},
                                    "location": {"type": "string"},
                                    "quote": {"type": "string"},
                                },
                            },
                        ]
                    },
                },
            },
        },
    },
    {
        "name": "get_legal_trace",
        "description": "按溯源编号读取完整的 Semantica 决策、来源、答案哈希和完整性校验结果。",
        "inputSchema": {
            "type": "object",
            "required": ["trace_id"],
            "properties": {"trace_id": {"type": "string"}},
        },
    },
    {
        "name": "search_legal_traces",
        "description": "只在用户明确要求回看已记录的法务答复时，按关键词检索本地 Semantica 决策索引。",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
        },
    },
    {
        "name": "get_audit_summary",
        "description": "返回本地 Semantica 溯源存储的计数和文件位置，不返回其他对话的内容。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "record_legal_answer":
        return STORE.record(arguments)
    if name == "get_legal_trace":
        return STORE.get(text(arguments.get("trace_id"), 100))
    if name == "search_legal_traces":
        return STORE.search(arguments.get("query"), min(max(int(arguments.get("limit", 10)), 1), 20))
    if name == "get_audit_summary":
        return STORE.summary()
    raise ValueError(f"Unknown tool: {name}")


def dispatch(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params") or {}
    if method == "initialize":
        return json_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "law-semantica-mcp", "version": "1.0.0"},
            },
        )
    if method == "tools/list":
        return json_response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        try:
            result = call_tool(params.get("name", ""), params.get("arguments") or {})
            return json_response(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
        except Exception as exc:
            return json_response(
                request_id,
                {"content": [{"type": "text", "text": json.dumps({"error": str(exc)}, ensure_ascii=False)}], "isError": True},
            )
    if method == "ping":
        return json_response(request_id, {})
    if request_id is None:
        return None
    return json_error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            response = dispatch(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as exc:
            print(json.dumps(json_error(None, -32700, f"Parse error: {exc}")), flush=True)
        except Exception as exc:
            print(json.dumps(json_error(None, -32603, str(exc))), flush=True)


if __name__ == "__main__":
    main()
