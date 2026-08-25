"""Small, dependency-free safety helpers shared by local MCP services."""

from __future__ import annotations

import asyncio
import atexit
import hashlib
import ipaddress
import json
import os
import re
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable
from urllib.parse import urlsplit, urlunsplit


MAX_QUERY_CHARS = 1_200
_LOCAL_HOSTS = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".private", ".corp", ".lan", ".home.arpa")


class AsyncRunner:
    """Run async-only upstream code on one long-lived event loop per process.

    Free Search owns Playwright and async locks globally. Calling its public
    coroutine functions with a new ``asyncio.run`` loop for every MCP request
    can bind those objects to a closed loop and leave a browser operation
    hanging. This runner serializes loop ownership while still allowing the
    MCP stdio loop to remain synchronous and simple.
    """

    def __init__(self, name: str) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._serve, name=name, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._loop is None:
            raise RuntimeError("async worker could not start")
        atexit.register(self.close)

    def _serve(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    async def _bounded(self, operation: Awaitable[Any], timeout_seconds: float) -> Any:
        return await asyncio.wait_for(operation, timeout=timeout_seconds)

    def run(self, operation: Awaitable[Any], *, timeout_seconds: float) -> Any:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        loop = self._loop
        if loop is None or loop.is_closed():
            raise RuntimeError("async worker is unavailable")
        future = asyncio.run_coroutine_threadsafe(self._bounded(operation, timeout_seconds), loop)
        try:
            # The small grace period allows asyncio cancellation/finalizers to
            # release a Playwright page before reporting a controlled timeout.
            return future.result(timeout=timeout_seconds + 5)
        except TimeoutError as exc:
            future.cancel()
            raise TimeoutError("async operation exceeded its time budget") from exc

    def close(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=3)


def clamp(value: Any, lower: int, upper: int, default: int) -> int:
    try:
        return max(lower, min(upper, int(value)))
    except (TypeError, ValueError):
        return default


def clean_query(value: Any, *, limit: int = MAX_QUERY_CHARS) -> str:
    query = " ".join(str(value or "").split())
    if not query:
        raise ValueError("query is required")
    if len(query) > limit:
        raise ValueError(f"query must not exceed {limit} characters")
    return query


def _public_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def validate_public_http_url(value: Any, *, max_length: int = 4_096) -> str:
    """Validate an absolute public HTTP(S) URL before a local service fetches it."""
    raw = str(value or "").strip()
    if not raw or len(raw) > max_length:
        raise ValueError("URL is missing or exceeds the safety limit")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL is invalid") from exc
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("only absolute http(s) URLs are allowed")
    if not host or parsed.username is not None or parsed.password is not None:
        raise ValueError("URL host and credentials are invalid")
    if port is not None and not 1 <= port <= 65_535:
        raise ValueError("URL port is invalid")
    if host in _LOCAL_HOSTS or host.endswith(_LOCAL_SUFFIXES):
        raise ValueError("local and private hostnames are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise ValueError("private, loopback, and reserved IP addresses are not allowed")
    else:
        try:
            addresses = {item[4][0].split("%", 1)[0] for item in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ValueError("URL hostname could not be resolved") from exc
        if not addresses or not all(_public_address(address) for address in addresses):
            raise ValueError("URL hostname resolves to a non-public address")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, parsed.query, ""))


def limited_text(value: Any, limit: int) -> str:
    text = str(value or "")
    return text[:limit]


def sanitize_error(error: BaseException | str) -> str:
    value = str(error)
    value = re.sub(r"(https?://)[^/@\s]+@", r"\1***@", value)
    value = re.sub(r"(?i)(api[_-]?key|token|secret|password)=([^&\s]+)", r"\1=***", value)
    return limited_text(value, 500)


def append_audit(audit_path: str | Path, *, service: str, action: str, subject: str, metadata: dict[str, Any]) -> None:
    """Write minimal local-only telemetry without retaining the query or URL itself."""
    path = Path(audit_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "action": action,
            "subject_sha256": hashlib.sha256(subject.encode("utf-8")).hexdigest(),
            **metadata,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.chmod(path, 0o600)
    except OSError:
        return
