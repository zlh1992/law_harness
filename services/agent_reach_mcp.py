#!/usr/bin/env python3
"""Harness-safe, read-only MCP adapter for selected Agent Reach channels."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import feedparser
import yt_dlp

from agent_reach import __version__ as AGENT_REACH_VERSION
from agent_reach.config import Config
from agent_reach.core import AgentReach
from agent_reach.channels.v2ex import V2EXChannel
from agent_reach.channels.web import WebChannel

try:  # Supports both `python services/agent_reach_mcp.py` and package tests.
    from mcp_utils import append_audit, clamp, clean_query, limited_text, sanitize_error, validate_public_http_url
except ModuleNotFoundError:  # pragma: no cover - exercised by the direct entrypoint above.
    from services.mcp_utils import append_audit, clamp, clean_query, limited_text, sanitize_error, validate_public_http_url


AUDIT_PATH = os.environ.get("AGENT_REACH_AUDIT_PATH", ".data/research/agent-reach-audit.jsonl")
MAX_OUTPUT_CHARS = 150_000
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_BVID = re.compile(r"^BV[0-9A-Za-z]{8,16}$")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


def _audit(action: str, subject: str, **metadata: Any) -> None:
    append_audit(AUDIT_PATH, service="agent_reach", action=action, subject=subject, metadata=metadata)


def _public_platform_url(value: Any, allowed_hosts: set[str] | None = None) -> str:
    url = validate_public_http_url(value)
    host = (urlsplit(url).hostname or "").lower()
    if allowed_hosts and host not in allowed_hosts:
        raise ValueError("URL host is not supported by this channel")
    return url


def _status(_: dict[str, Any]) -> dict[str, Any]:
    report = AgentReach(Config(read_only=True)).doctor()
    selected = {name: report.get(name) for name in ("web", "youtube", "bilibili", "v2ex", "rss", "github") if name in report}
    return {"service": "agent-reach-readonly", "version": AGENT_REACH_VERSION, "channels": selected, "mutates_remote_state": False}


def _read_web(args: dict[str, Any]) -> dict[str, Any]:
    url = _public_platform_url(args.get("url"))
    text = WebChannel().read(url)
    result = {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(), "content": limited_text(text, MAX_OUTPUT_CHARS)}
    _audit("read_web", url, result_chars=len(result["content"]))
    return result


def _youtube(args: dict[str, Any]) -> dict[str, Any]:
    url = _public_platform_url(args.get("url"), _YOUTUBE_HOSTS)
    mode = args.get("mode", "metadata")
    if mode not in {"metadata", "subtitles"}:
        raise ValueError("mode must be metadata or subtitles")
    languages = args.get("languages")
    if not isinstance(languages, list):
        languages = ["zh-Hans", "zh", "en"]
    languages = [str(language)[:32] for language in languages[:5] if str(language).strip()] or ["zh-Hans", "zh", "en"]
    common = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30, "skip_download": True}
    if mode == "metadata":
        with yt_dlp.YoutubeDL(common) as client:
            raw = client.extract_info(url, download=False)
        result = {
            "url": url,
            "id": raw.get("id"),
            "title": raw.get("title"),
            "channel": raw.get("channel") or raw.get("uploader"),
            "duration_seconds": raw.get("duration"),
            "upload_date": raw.get("upload_date"),
            "description": limited_text(raw.get("description"), 12_000),
            "webpage_url": raw.get("webpage_url") or url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        with tempfile.TemporaryDirectory(prefix="law-harness-ytdlp-") as directory:
            options = {
                **common,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": languages,
                "subtitlesformat": "vtt",
                "outtmpl": str(Path(directory) / "%(id)s.%(ext)s"),
            }
            with yt_dlp.YoutubeDL(options) as client:
                raw = client.extract_info(url, download=True)
            files = sorted(Path(directory).glob("*.vtt"))
            if not files:
                raise RuntimeError("no requested public subtitles are available")
            subtitle = files[0].read_text(encoding="utf-8", errors="replace")
        result = {
            "url": url,
            "id": raw.get("id"),
            "title": raw.get("title"),
            "language": files[0].suffixes[-2].lstrip(".") if len(files[0].suffixes) > 1 else "unknown",
            "subtitles_vtt": limited_text(subtitle, MAX_OUTPUT_CHARS),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    _audit("youtube", url, mode=mode)
    return result


def _bilibili_api(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.bilibili.com{path}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "law-harness-agent-reach/1.0"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read(2_000_000))
    if payload.get("code") != 0:
        raise RuntimeError("Bilibili public API did not return a successful response")
    return payload.get("data") or {}


def _bilibili(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "search")
    limit = clamp(args.get("limit"), 1, 10, 5)
    raw_value = str(args.get("query_or_id") or "").strip()
    if action == "search":
        query = clean_query(raw_value)
        data = _bilibili_api("/x/web-interface/search/type", {"search_type": "video", "keyword": query, "page": 1, "page_size": limit})
        result = {"action": action, "query": query, "items": [{"title": limited_text(item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""), 500), "bvid": item.get("bvid"), "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}", "description": limited_text(item.get("description"), 1_500), "author": item.get("author"), "duration": item.get("duration")} for item in (data.get("result") or [])[:limit]]}
    elif action == "hot":
        data = _bilibili_api("/x/web-interface/popular", {"pn": 1, "ps": limit})
        result = {"action": action, "items": [{"title": item.get("title"), "bvid": item.get("bvid"), "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}", "description": limited_text(item.get("desc"), 1_500), "owner": (item.get("owner") or {}).get("name")} for item in (data.get("list") or [])[:limit]]}
    elif action == "video":
        if not _BVID.fullmatch(raw_value):
            raise ValueError("video lookup requires a valid BV identifier")
        data = _bilibili_api("/x/web-interface/view", {"bvid": raw_value})
        result = {"action": action, "bvid": raw_value, "url": f"https://www.bilibili.com/video/{raw_value}", "title": data.get("title"), "description": limited_text(data.get("desc"), 12_000), "owner": (data.get("owner") or {}).get("name"), "published_at": data.get("pubdate"), "duration_seconds": data.get("duration")}
    else:
        raise ValueError("action must be search, hot, or video")
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    _audit("bilibili", raw_value or action, channel_action=action, item_count=len(result.get("items") or []))
    return result


def _v2ex(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "hot")
    identifier = str(args.get("identifier") or "").strip()
    limit = clamp(args.get("limit"), 1, 20, 10)
    channel = V2EXChannel()
    if action == "hot":
        result: Any = channel.get_hot_topics(limit)
    elif action == "node":
        if not _SAFE_NAME.fullmatch(identifier):
            raise ValueError("node identifier is invalid")
        result = channel.get_node_topics(identifier, limit)
    elif action == "topic":
        if not identifier.isdigit() or not 0 < int(identifier) < 2_147_483_647:
            raise ValueError("topic identifier is invalid")
        result = channel.get_topic(int(identifier))
    elif action == "user":
        if not _SAFE_NAME.fullmatch(identifier):
            raise ValueError("user identifier is invalid")
        result = channel.get_user(identifier)
    else:
        raise ValueError("action must be hot, node, topic, or user")
    _audit("v2ex", identifier or action, channel_action=action)
    return {"action": action, "identifier": identifier or None, "fetched_at": datetime.now(timezone.utc).isoformat(), "result": result}


def _rss_read(args: dict[str, Any]) -> dict[str, Any]:
    url = _public_platform_url(args.get("url"))
    limit = clamp(args.get("limit"), 1, 20, 10)
    feed = feedparser.parse(url)
    if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
        raise RuntimeError("RSS/Atom feed could not be parsed")
    entries = []
    for entry in (feed.entries or [])[:limit]:
        entries.append({"title": limited_text(entry.get("title"), 500), "url": entry.get("link"), "published": entry.get("published") or entry.get("updated"), "summary": limited_text(entry.get("summary") or entry.get("description"), 4_000)})
    result = {"url": url, "title": limited_text((feed.feed or {}).get("title"), 500), "entries": entries, "fetched_at": datetime.now(timezone.utc).isoformat()}
    _audit("rss_read", url, entry_count=len(entries))
    return result


TOOLS = [
    {"name": "status", "description": "检查 Agent Reach 匿名只读渠道状态；不读取 Cookie 或密钥。", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_web", "description": "通过 Agent Reach 的 Jina Reader 读取一个公开网页。", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}}},
    {"name": "youtube", "description": "读取公开 YouTube 视频元数据或字幕；不下载媒体、播放列表或 Cookie。", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "mode": {"enum": ["metadata", "subtitles"]}, "languages": {"type": "array", "maxItems": 5, "items": {"type": "string"}}}}},
    {"name": "bilibili", "description": "通过 B站公开 API 搜索、读取热门视频或指定 BV 视频详情。", "inputSchema": {"type": "object", "properties": {"action": {"enum": ["search", "hot", "video"]}, "query_or_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}}},
    {"name": "v2ex", "description": "读取 V2EX 公开热门、节点、主题或用户信息。", "inputSchema": {"type": "object", "properties": {"action": {"enum": ["hot", "node", "topic", "user"]}, "identifier": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}}},
    {"name": "rss_read", "description": "读取公开 RSS/Atom 源，最多返回 20 条。", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}}},
]

OPERATIONS: dict[str, Callable[[dict[str, Any]], Any]] = {"status": _status, "read_web": _read_web, "youtube": _youtube, "bilibili": _bilibili, "v2ex": _v2ex, "rss_read": _rss_read}


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
                respond(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "law-harness-agent-reach", "version": "1.0.0"}})
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
