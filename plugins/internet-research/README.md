# Internet Research Plugin for DeepSeek Harness

This deployment uses the official `@deepseek-ai/dsh-mcp-client` Cordis plugin to mount three local, read-only MCP servers: the weighted `internet_research` router, a restricted `free_search` follow-up reader, and an `agent_reach` public-platform adapter.

## Tools

- `mcp__internet_research__simple_search`: one query, one weighted provider route.
- `mcp__internet_research__deep_research`: 2–8 subqueries in a bounded parallel batch, one weighted route per subquery, URL deduplication, source ranking, and a structured evidence packet.
- `mcp__internet_research__status`: configuration diagnostics without network access or credential disclosure.
- `mcp__free_search__fetch`, `fetch_batch`, `read_doc`, `cache_search`, `compare`, `extract_structured`, and `engines`: read a known public URL or the local cache after the router has discovered it. It deliberately does not expose Free Search's direct `search`, `research`, or `download` operations.
- `mcp__agent_reach__read_web`, `youtube`, `bilibili`, `v2ex`, and `rss_read`: fixed, anonymous, public and read-only Agent Reach channels. There is no generic shell, account, Cookie, message, media-download, or write operation.

Routing is Free Search 50%, Tavily 30%, Exa 10%, and SerpAPI 10%. Every primary provider error goes first to Tavily; a Tavily error goes second to Free Search. The chain is capped at three attempts. A transient primary Tavily failure is retried once; a permanently unavailable Tavily key/auth route skips that duplicate attempt and proceeds to Free Search.

Free Search and Agent Reach are installed from pinned, SHA-256-verified GitHub release tarballs by `install/install-internet-tools.sh` into the ignored `.tools/upstreams/` tree. They run with separate virtual environments on this Mac. Paid-provider secrets live in `.env.research`, are passed only to the Host-side router, and never enter the browser bundle, model-visible results, or audit log. Local audit files retain only hashes plus routing/count metadata.

The referenced `uni_miroflow` checkout contains empty search/agent implementation placeholders. This plugin reuses its working architectural ideas: MCP discovery, a persistent server process, bounded concurrency, timeouts, failure recovery, and structured research reports.
