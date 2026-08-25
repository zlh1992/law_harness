# DSH LLM Wiki Knowledge Graph

DeepSeek Harness Cordis Host/Client plugin for a read-only view of the local legal OKF Wiki.

- Host route: `GET /api/law-wiki-graph?sessionId=...`
- Client slot: `conversation.session.header.utilities`
- Highlight source: successful `mcp__law_wiki__read_page` and `mcp__law_wiki__okf_read_concept` call/result pairs in the selected DSH Session event log
- OKF graph fields: stable concept ID, `type`, `status`, `tags`, `law.jurisdictions`, derived trust signal, standard Markdown links, and package-internal `sources[].resource` links
- Client controls: search, type/trust/session-read filters, selected-node metadata, local-neighbour focus, pan and zoom
- Header placement: `Wiki 图谱` is a persistent right-side Session utility, ordered directly after the built-in Session Log action; it is rendered before any Wiki call has completed
- Data boundary: titles, relative Wiki paths, metadata summaries, relation targets, source registrations, and usage counters only; no document body or absolute host path is returned

This plugin never writes to the Wiki or to Session history.
