#!/usr/bin/env python3
"""Read-only mixed internet-research MCP server for DeepSeek Harness.

Each query selects one provider: Free Search 50%, Tavily 30%, Exa 10%, or
SerpAPI 10%. Failures are bounded: Tavily is the first fallback and Free Search
the second. This process runs in Free Search's isolated Python environment, so
its keyless multi-engine implementation is invoked locally without an HTTP port.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import random
import re
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:  # Supports both `python services/internet_research_mcp.py` and package tests.
    from mcp_utils import AsyncRunner
except ModuleNotFoundError:  # pragma: no cover - exercised by the direct entrypoint above.
    from services.mcp_utils import AsyncRunner


TAVILY_ENDPOINT = "https://api.tavily.com/search"
EXA_ENDPOINT = "https://api.exa.ai/search"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
ROUTING_POLICY = {"free_search": 0.50, "tavily": 0.30, "exa": 0.10, "serpapi": 0.10}
MAX_QUERY_CHARS = 1_200
MAX_EVIDENCE_CHARS = 1_400
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("INTERNET_RESEARCH_PROVIDER_TIMEOUT_SECONDS", "12"))
FREE_SEARCH_SIMPLE_TIMEOUT_SECONDS = float(os.environ.get("INTERNET_RESEARCH_FREE_SEARCH_SIMPLE_TIMEOUT_SECONDS", "40"))
FREE_SEARCH_DEEP_TIMEOUT_SECONDS = float(os.environ.get("INTERNET_RESEARCH_FREE_SEARCH_DEEP_TIMEOUT_SECONDS", "20"))
DEEP_RESEARCH_TIME_BUDGET_SECONDS = float(os.environ.get("INTERNET_RESEARCH_DEEP_TIME_BUDGET_SECONDS", "75"))
USER_AGENT = "law-harness-internet-research/1.0"
_free_search_runner: AsyncRunner | None = None


class ProviderError(RuntimeError):
    """A provider request failed without exposing credentials or response bodies."""


@dataclass(frozen=True)
class ProviderKeys:
    tavily: str
    exa: str
    serpapi: str

    @classmethod
    def from_env(cls) -> "ProviderKeys":
        return cls(
            tavily=os.environ.get("TAVILY_API_KEY", "").strip(),
            exa=os.environ.get("EXA_API_KEY", "").strip(),
            serpapi=os.environ.get("SERPAPI_API_KEY", "").strip(),
        )

    def require(self, provider: str) -> str:
        value = getattr(self, provider)
        if not value:
            raise ProviderError(f"{provider} API key is not configured")
        return value

    def configured(self) -> dict[str, bool]:
        return {
            "free_search": os.environ.get("FREE_SEARCH_AVAILABLE", "true").strip().lower() not in {"0", "false", "no"},
            "tavily": bool(self.tavily),
            "exa": bool(self.exa),
            "serpapi": bool(self.serpapi),
        }


def clamp(value: Any, lower: int, upper: int, default: int) -> int:
    try:
        return max(lower, min(upper, int(value)))
    except (TypeError, ValueError):
        return default


def clean_query(value: Any) -> str:
    query = " ".join(str(value or "").split())
    if not query:
        raise ValueError("query is required")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must not exceed {MAX_QUERY_CHARS} characters")
    return query


def excerpt(value: Any, limit: int = MAX_EVIDENCE_CHARS) -> str:
    text = html.unescape(re.sub(r"\s+", " ", str(value or ""))).strip()
    return text[:limit]


def choose_provider(rng: random.Random | random.SystemRandom | None = None) -> str:
    value = (rng or random.SystemRandom()).random()
    cumulative = 0.0
    for provider, weight in ROUTING_POLICY.items():
        cumulative += weight
        if value < cumulative:
            return provider
    return next(reversed(ROUTING_POLICY))


def request_json(
    provider: str,
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if params:
        url = f"{url}?{urlencode(params)}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(5_000_000)
    except HTTPError as exc:
        raise ProviderError(f"{provider} returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"{provider} transport failure: {type(exc).__name__}") from exc
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderError(f"{provider} returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProviderError(f"{provider} returned an invalid response shape")
    if value.get("error"):
        raise ProviderError(f"{provider} reported an API error")
    return value


def normalize_result(
    *,
    provider: str,
    title: Any,
    url: Any,
    text: Any,
    published_at: Any = None,
    score: Any = None,
) -> dict[str, Any] | None:
    link = str(url or "").strip()
    if not link.startswith(("https://", "http://")):
        return None
    result: dict[str, Any] = {
        "title": excerpt(title, 300) or link,
        "url": link,
        "excerpt": excerpt(text),
        "provider": provider,
    }
    if published_at:
        result["published_at"] = excerpt(published_at, 120)
    if isinstance(score, (int, float)):
        result["provider_score"] = round(float(score), 6)
    return result


def search_tavily(query: str, max_results: int, *, deep: bool, keys: ProviderKeys) -> list[dict[str, Any]]:
    data = request_json(
        "tavily",
        TAVILY_ENDPOINT,
        method="POST",
        headers={"Content-Type": "application/json"},
        payload={
            "api_key": keys.require("tavily"),
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced" if deep else "basic",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    normalized = []
    for item in data.get("results") or []:
        result = normalize_result(
            provider="tavily",
            title=item.get("title"),
            url=item.get("url"),
            text=item.get("content"),
            published_at=item.get("published_date"),
            score=item.get("score"),
        )
        if result:
            normalized.append(result)
    return normalized[:max_results]


def search_exa(query: str, max_results: int, *, deep: bool, keys: ProviderKeys) -> list[dict[str, Any]]:
    data = request_json(
        "exa",
        EXA_ENDPOINT,
        method="POST",
        headers={"Content-Type": "application/json", "x-api-key": keys.require("exa")},
        payload={
            "query": query,
            "numResults": max_results,
            "type": "neural",
            "contents": {"text": {"maxCharacters": 4_000 if deep else 1_500}, "highlights": True},
        },
    )
    normalized = []
    for item in data.get("results") or []:
        highlights = item.get("highlights") or []
        evidence = item.get("text") or " ".join(str(value) for value in highlights)
        result = normalize_result(
            provider="exa",
            title=item.get("title"),
            url=item.get("url"),
            text=evidence,
            published_at=item.get("publishedDate"),
            score=item.get("score"),
        )
        if result:
            normalized.append(result)
    return normalized[:max_results]


def search_serpapi(query: str, max_results: int, *, deep: bool, keys: ProviderKeys) -> list[dict[str, Any]]:
    del deep
    data = request_json(
        "serpapi",
        SERPAPI_ENDPOINT,
        params={
            "api_key": keys.require("serpapi"),
            "engine": "google",
            "q": query,
            "num": max_results,
            "hl": "en",
            "gl": "us",
        },
    )
    normalized = []
    for item in data.get("organic_results") or []:
        result = normalize_result(
            provider="serpapi",
            title=item.get("title"),
            url=item.get("link"),
            text=item.get("snippet") or item.get("snippet_highlighted_words"),
            published_at=item.get("date"),
            score=None,
        )
        if result:
            normalized.append(result)
    return normalized[:max_results]


def search_free_search(query: str, max_results: int, *, deep: bool, keys: ProviderKeys) -> list[dict[str, Any]]:
    """Use the locally installed keyless Free Search implementation.

    `deep` is deliberately not mapped to Free Search's one-shot `research`:
    this router owns subquery planning and normalises every route to the same
    evidence shape before cross-provider ranking.
    """
    del keys
    try:
        from search_mcp import server as free_search_server
    except ImportError as exc:
        raise ProviderError("free_search is not installed") from exc
    try:
        timeout = FREE_SEARCH_DEEP_TIMEOUT_SECONDS if deep else FREE_SEARCH_SIMPLE_TIMEOUT_SECONDS
        global _free_search_runner
        if _free_search_runner is None:
            _free_search_runner = AsyncRunner("internet-research-free-search")
        payload = _free_search_runner.run(
            free_search_server.search(
                query=query,
                max_results=max_results,
                use_cache=True,
                format="json",
            ),
            timeout_seconds=timeout,
        )
    except Exception as exc:
        raise ProviderError(f"free_search failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ProviderError("free_search returned an invalid response shape")
    normalized = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        result = normalize_result(
            provider="free_search",
            title=item.get("title"),
            url=item.get("url"),
            text=item.get("snippet") or item.get("lead_snippet"),
            published_at=item.get("published_at") or item.get("date"),
            score=item.get("score"),
        )
        if result:
            normalized.append(result)
    return normalized[:max_results]


PROVIDER_SEARCH: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "free_search": search_free_search,
    "tavily": search_tavily,
    "exa": search_exa,
    "serpapi": search_serpapi,
}


def search_provider(
    provider: str,
    query: str,
    max_results: int,
    *,
    deep: bool = False,
    keys: ProviderKeys | None = None,
) -> list[dict[str, Any]]:
    if provider not in PROVIDER_SEARCH:
        raise ValueError(f"unknown provider: {provider}")
    results = PROVIDER_SEARCH[provider](query, max_results, deep=deep, keys=keys or ProviderKeys.from_env())
    if not results:
        raise ProviderError(f"{provider} returned no usable results")
    return results


def run_routed_search(
    query: str,
    max_results: int,
    *,
    deep: bool = False,
    rng: random.Random | random.SystemRandom | None = None,
    selected_provider: str | None = None,
    search_fn: Callable[..., list[dict[str, Any]]] = search_provider,
) -> dict[str, Any]:
    selected = selected_provider or choose_provider(rng)
    attempts: list[dict[str, Any]] = []

    def attempt(provider: str, stage: str) -> list[dict[str, Any]]:
        started = time.monotonic()
        try:
            results = search_fn(provider, query, max_results, deep=deep)
            attempts.append({
                "provider": provider,
                "stage": stage,
                "status": "ok",
                "duration_ms": round((time.monotonic() - started) * 1_000),
                "result_count": len(results),
            })
            return results
        except Exception as exc:
            attempts.append({
                "provider": provider,
                "stage": stage,
                "status": "error",
                "error": type(exc).__name__,
                "duration_ms": round((time.monotonic() - started) * 1_000),
            })
            raise

    def permanently_unavailable(error: Exception) -> bool:
        message = str(error).lower()
        return "not configured" in message or "http 401" in message or "http 403" in message

    try:
        results = attempt(selected, "primary")
        used = selected
        fallback_level = 0
    except Exception as primary_error:
        # The first fallback is always Tavily. If Tavily was the selected route,
        # retry only a potentially transient failure; a missing/invalid key is
        # deterministically skipped to the second-layer Free Search fallback.
        try:
            if selected == "tavily" and permanently_unavailable(primary_error):
                raise ProviderError("Tavily is permanently unavailable") from primary_error
            results = attempt("tavily", "tavily_fallback")
            used = "tavily"
            fallback_level = 1
        except Exception as tavily_error:
            try:
                # This is intentionally attempted even if Free Search was the
                # primary route: it is a single bounded retry after Tavily.
                results = attempt("free_search", "free_search_fallback")
                used = "free_search"
                fallback_level = 2
            except Exception as free_search_error:
                raise ProviderError(
                    f"selected route {selected}, Tavily fallback, and Free Search fallback all failed "
                    f"({type(primary_error).__name__}, {type(tavily_error).__name__}, {type(free_search_error).__name__})"
                ) from free_search_error

    return {
        "query": query,
        "selected_provider": selected,
        "provider_used": used,
        "fallback_used": fallback_level > 0,
        "fallback_level": fallback_level,
        "attempts": attempts,
        "results": results,
        "result_count": len(results),
    }


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    query = [(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}]
    path_value = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path_value, urlencode(query), ""))


def looks_primary(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host.endswith((".gov", ".gov.cn", ".europa.eu", ".org")) or host in {
        "www.sec.gov",
        "www.gov.cn",
        "www.cac.gov.cn",
        "www.samr.gov.cn",
        "www.court.gov.cn",
    }


def default_subqueries(query: str, breadth: int) -> list[str]:
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", query))
    suffixes = (
        ["官方文件 原始来源", "最新进展 时间线", "专业分析 争议 风险", "监管机构 指引 实务", "数据 证据 反例", "跨法域 比较"]
        if has_cjk
        else ["official primary sources", "latest developments timeline", "expert analysis controversy risks", "regulator guidance practice", "data evidence counterexamples", "cross jurisdiction comparison"]
    )
    return [query, *[f"{query} {suffix}" for suffix in suffixes]][:breadth]


def research_subqueries(query: str, provided: Any, breadth: int) -> list[str]:
    candidates = provided if isinstance(provided, list) else []
    cleaned: list[str] = []
    for item in candidates:
        try:
            value = clean_query(item)
        except ValueError:
            continue
        if value not in cleaned:
            cleaned.append(value)
    if not cleaned:
        cleaned = default_subqueries(query, breadth)
    return cleaned[:breadth]


def append_audit(mode: str, query: str, payload: dict[str, Any]) -> None:
    audit_path = Path(os.environ.get("RESEARCH_AUDIT_PATH", ".data/research/search-audit.jsonl"))
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            **payload,
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.chmod(audit_path, 0o600)
    except OSError:
        # Search remains available if local audit storage is temporarily unavailable.
        return


def simple_search(args: dict[str, Any]) -> dict[str, Any]:
    query = clean_query(args.get("query"))
    max_results = clamp(args.get("max_results"), 1, 10, 5)
    routed = run_routed_search(query, max_results, deep=False)
    output = {
        "mode": "simple",
        "live_web": True,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "routing_policy": ROUTING_POLICY,
        **routed,
    }
    append_audit("simple", query, {
        "selected_provider": routed["selected_provider"],
        "provider_used": routed["provider_used"],
        "fallback_used": routed["fallback_used"],
        "result_count": routed["result_count"],
    })
    return output


def deep_research(
    args: dict[str, Any],
    *,
    route_fn: Callable[..., dict[str, Any]] = run_routed_search,
    time_budget_seconds: float | None = None,
) -> dict[str, Any]:
    query = clean_query(args.get("query"))
    breadth = clamp(args.get("breadth"), 2, 8, 4)
    max_results = clamp(args.get("max_results_per_query"), 2, 8, 5)
    subqueries = research_subqueries(query, args.get("subqueries"), breadth)
    budget = DEEP_RESEARCH_TIME_BUDGET_SECONDS if time_budget_seconds is None else max(0.01, float(time_budget_seconds))
    deadline = time.monotonic() + budget
    routed_by_query: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    def execute(subquery: str) -> tuple[str, dict[str, Any]]:
        return subquery, route_fn(subquery, max_results, deep=True)

    # Do not let one slow keyless/browser route hold the model tool call open
    # past the web gateway's request lifetime. Four complementary searches are
    # still enough to build a useful evidence packet; outstanding work is
    # marked in the returned coverage instead of converting the whole tool call
    # into a timeout.
    executor = ThreadPoolExecutor(max_workers=min(4, len(subqueries)), thread_name_prefix="research-search")
    futures = {executor.submit(execute, subquery): subquery for subquery in subqueries}
    pending = set(futures)
    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            completed, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not completed:
                break
            for future in completed:
                subquery = futures[future]
                try:
                    resolved, routed = future.result()
                    routed_by_query[resolved] = routed
                except Exception as exc:
                    failures.append({"query": subquery, "error": type(exc).__name__})
    finally:
        for future in pending:
            future.cancel()
        # Provider requests have their own finite budgets. Do not wait for any
        # last cancellation cleanup here: return completed evidence immediately.
        executor.shutdown(wait=False, cancel_futures=True)

    for future in pending:
        failures.append({"query": futures[future], "error": "time_budget_exceeded"})

    sources: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    for subquery in subqueries:
        routed = routed_by_query.get(subquery)
        if not routed:
            continue
        trace.append({
            "query": subquery,
            "selected_provider": routed["selected_provider"],
            "provider_used": routed["provider_used"],
            "fallback_used": routed["fallback_used"],
            "result_count": routed["result_count"],
        })
        for rank, result in enumerate(routed["results"], start=1):
            key = canonical_url(result["url"])
            entry = sources.get(key)
            if entry is None:
                entry = {
                    **result,
                    "url": key,
                    "matched_queries": [],
                    "providers": [],
                    "best_rank": rank,
                    "primary_source_hint": looks_primary(key),
                }
                sources[key] = entry
            if subquery not in entry["matched_queries"]:
                entry["matched_queries"].append(subquery)
            if result["provider"] not in entry["providers"]:
                entry["providers"].append(result["provider"])
            entry["best_rank"] = min(entry["best_rank"], rank)
            if len(result.get("excerpt", "")) > len(entry.get("excerpt", "")):
                entry["excerpt"] = result["excerpt"]

    ranked = sorted(
        sources.values(),
        key=lambda item: (
            -len(item["matched_queries"]),
            -int(item["primary_source_hint"]),
            item["best_rank"],
            item["url"],
        ),
    )[: min(40, breadth * max_results)]
    for index, item in enumerate(ranked, start=1):
        item["source_id"] = f"S{index}"

    output = {
        "mode": "deep_research",
        "live_web": True,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "research_plan": [
            {"subquery": subquery, "purpose": "独立检索并形成可交叉核验的证据切面"}
            for subquery in subqueries
        ],
        "routing_policy": ROUTING_POLICY,
        "routing_trace": trace,
        "coverage": {
            "time_budget_seconds": budget,
            "elapsed_ms": round((time.monotonic() - (deadline - budget)) * 1_000),
            "planned_queries": len(subqueries),
            "successful_queries": len(routed_by_query),
            "failed_queries": len(failures),
            "unique_sources": len(ranked),
            "primary_source_hints": sum(1 for item in ranked if item["primary_source_hint"]),
        },
        "failures": failures,
        "sources": ranked,
        "instructions": [
            "综合时应逐项引用 source_id、标题与 URL，不得引用未出现在 sources 中的链接。",
            "搜索摘要不是正式法律权威；涉及法条、监管状态或期限时优先核对 primary_source_hint 的官方来源。",
            "如关键问题覆盖不足，应针对缺口再次调用 deep_research，而不是补造结论。",
        ],
    }
    append_audit("deep_research", query, {
        "planned_queries": len(subqueries),
        "successful_queries": len(routed_by_query),
        "failed_queries": len(failures),
        "unique_sources": len(ranked),
        "time_budget_seconds": budget,
        "elapsed_ms": round((time.monotonic() - (deadline - budget)) * 1_000),
        "fallback_count": sum(1 for item in trace if item["fallback_used"]),
        "provider_counts": {
            provider: sum(1 for item in trace if item["provider_used"] == provider)
            for provider in ROUTING_POLICY
        },
    })
    return output


def status(_: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": "internet-research-mixed-readonly",
        "version": "2.0.0",
        "configured": ProviderKeys.from_env().configured(),
        "routing_policy": ROUTING_POLICY,
        "fallback_chain": ["tavily", "free_search"],
        "maximum_attempts": 3,
        "mutates_remote_state": False,
        "note": "Free Search is local and keyless; Tavily, Exa and SerpAPI remain optional configured routes.",
    }


TOOLS = [
    {
        "name": "simple_search",
        "description": "简单、单一事实或快速时效查询使用。每次按 Free Search 50% / Tavily 30% / Exa 10% / SerpAPI 10% 选择一路；首选失败先回退 Tavily，Tavily 失败再回退 Free Search，最多三次。返回真实网页标题、URL、摘要和完整尝试链。",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "maxLength": MAX_QUERY_CHARS},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
        },
    },
    {
        "name": "deep_research",
        "description": "复杂、时效性强、需比较/交叉核验/多来源证据的问题使用。先把主问题分成 3–6 个互补 subqueries；每个子问题按 Free Search 50% / Tavily 30% / Exa 10% / SerpAPI 10% 独立路由，失败依次回退 Tavily、Free Search；随后按 URL 去重、标出官方来源提示并返回研究证据包。",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "maxLength": MAX_QUERY_CHARS},
                "subqueries": {"type": "array", "minItems": 2, "maxItems": 8, "items": {"type": "string", "maxLength": MAX_QUERY_CHARS}},
                "breadth": {"type": "integer", "minimum": 2, "maximum": 8},
                "max_results_per_query": {"type": "integer", "minimum": 2, "maximum": 8},
            },
        },
    },
    {
        "name": "status",
        "description": "诊断 Free Search、Tavily、Exa、SerpAPI 的可用配置、权重及兜底链；绝不返回 API 密钥，也不发起联网请求。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def respond(request_id: Any, result: Any) -> None:
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False), flush=True)


def main() -> None:
    operations = {"simple_search": simple_search, "deep_research": deep_research, "status": status}
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params") or {}
            if method == "initialize":
                respond(request_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "internet-research-readonly", "version": "1.0.0"},
                })
            elif method == "tools/list":
                respond(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                try:
                    result = operations[params.get("name")](params.get("arguments") or {})
                    respond(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
                except Exception as exc:
                    respond(request_id, {
                        "content": [{"type": "text", "text": json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False)}],
                        "isError": True,
                    })
            elif method == "ping":
                respond(request_id, {})
            elif request_id is not None:
                print(json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(exc)},
            }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
