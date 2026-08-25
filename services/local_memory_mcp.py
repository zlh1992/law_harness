#!/usr/bin/env python3
"""A small local-only SQLite Memory MCP server for the public law assistant.

It is deliberately explicit: the agent is instructed to call it only when the
user asks to remember or recall something.  No cloud API or embedding model is
used, so confidential data stays in the local SQLite file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("MEMORY_DB_PATH", ROOT / ".data" / "memory" / "memory.db"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: Any, lower: int, upper: int, default: int) -> int:
    try:
        return max(lower, min(upper, int(value)))
    except (TypeError, ValueError):
        return default


class MemoryStore:
    def __init__(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.connection:
            self.connection.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            self.connection.execute("CREATE INDEX IF NOT EXISTS idx_memories_updated_at ON memories(updated_at DESC)")

    @staticmethod
    def item(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "content": row["content"],
            "tags": json.loads(row["tags"]),
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def remember(self, args: dict[str, Any]) -> dict[str, Any]:
        content = str(args.get("content") or "").strip()
        if not content:
            raise ValueError("content is required")
        if len(content) > 8000:
            raise ValueError("content must be no longer than 8000 characters")
        raw_tags = args.get("tags") or []
        if not isinstance(raw_tags, list):
            raise ValueError("tags must be an array of strings")
        tags = [str(tag).strip()[:80] for tag in raw_tags[:20] if str(tag).strip()]
        item_id = f"memory-{uuid.uuid4().hex[:16]}"
        timestamp = now()
        importance = clamp(args.get("importance"), 1, 5, 3)
        with self.lock, self.connection:
            self.connection.execute(
                "INSERT INTO memories(id, content, tags, importance, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, content, json.dumps(tags, ensure_ascii=False), importance, timestamp, timestamp),
            )
        return {"id": item_id, "status": "remembered", "tags": tags, "importance": importance}

    def recall(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        limit = clamp(args.get("limit"), 1, 20, 8)
        terms = [term for term in query.lower().split() if len(term) > 1][:8]
        with self.lock:
            rows = self.connection.execute("SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT 200").fetchall()
        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            item = self.item(row)
            haystack = (item["content"] + " " + " ".join(item["tags"])).lower()
            score = sum(term in haystack for term in terms)
            if query.lower() in haystack:
                score += 4
            if score:
                scored.append((score * 10 + item["importance"], item))
        scored.sort(key=lambda pair: (pair[0], pair[1]["updated_at"]), reverse=True)
        return {"memories": [item for _, item in scored[:limit]], "count": min(len(scored), limit), "local_only": True}

    def recent(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = clamp(args.get("limit"), 1, 20, 10)
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"memories": [self.item(row) for row in rows], "count": len(rows), "local_only": True}

    def forget(self, args: dict[str, Any]) -> dict[str, Any]:
        item_id = str(args.get("id") or "").strip()
        if not item_id:
            raise ValueError("id is required")
        with self.lock, self.connection:
            deleted = self.connection.execute("DELETE FROM memories WHERE id = ?", (item_id,)).rowcount
        return {"id": item_id, "deleted": bool(deleted)}


STORE = MemoryStore()
TOOLS = [
    {
        "name": "remember_fact",
        "description": "仅在用户明确要求记住时，将一条已脱敏的偏好、事项事实或待办保存到本机 SQLite 记忆。禁止保存身份证号、完整合同、商业秘密或未脱敏个人信息。",
        "inputSchema": {
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "importance": {"type": "integer", "minimum": 1, "maximum": 5},
            },
        },
    },
    {
        "name": "recall",
        "description": "仅在用户明确要求回忆时，在本机 SQLite 记忆中按关键词检索。检索结果不得泄露当前对话未确认的客户、个人或案件信息。",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
        },
    },
    {
        "name": "list_recent_memories",
        "description": "仅在用户明确要求查看近期记忆时列出本机 SQLite 记忆。",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}}},
    },
    {
        "name": "forget",
        "description": "按记忆 ID 删除用户明确要求删除的本地记忆。",
        "inputSchema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
    },
]


def respond(request_id: Any, result: Any) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False), flush=True)


def main() -> None:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params") or {}
            if method == "initialize":
                respond(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "law-local-memory", "version": "1.0.0"}})
            elif method == "tools/list":
                respond(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                operations = {"remember_fact": STORE.remember, "recall": STORE.recall, "list_recent_memories": STORE.recent, "forget": STORE.forget}
                try:
                    result = operations[params.get("name")](params.get("arguments") or {})
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
                except Exception as exc:
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps({"error": str(exc)}, ensure_ascii=False)}], "isError": True})
            elif method == "ping":
                respond(request_id, {})
            elif request_id is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
