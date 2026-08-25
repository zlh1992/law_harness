# Session Files plugin

DeepSeek Harness dual-half Cordis plugin for conversation-scoped document input.

## Trust boundary

- Loopback UI (`127.0.0.1` / `localhost`): the user pastes an absolute Mac path. The Host validates and records the resolved regular file; no bytes are copied.
- Public UI: the browser sends raw file bytes only to the authenticated public gateway. The gateway validates the session id, extension and quotas, then stores the file at `workspaces/session-files/<sessionId>/uploads/` with mode `0600`.
- The browser and model receive only a random `file_id`, not a general filesystem capability.
- `session_file_list` and `session_file_read` derive the real Session id from the executing Agent and can resolve only records under that Session.
- Files are never executed. Public uploads use an extension allowlist and default to 25 MB per file / 250 MB per Session.

## Harness integration

- Host routes:
  - `GET|HEAD /api/session-files?sessionId=...`
  - `POST /api/session-files/local-reference` (blocked by the public gateway)
- Public gateway route:
  - `POST /api/session-files/upload`
- Client slot: `conversation.input.left`
- Model tools:
  - `session_file_list()`
  - `session_file_read(file_id, offset?, limit?)`

Text, PDF, DOCX, XLSX and PPTX extraction runs locally on the Mac. Legacy DOC/RTF/ODT uses macOS `textutil`. Images continue to use Harness's built-in image attachment path.

## Operations

The runtime root defaults to `workspaces/session-files`. To override it, set the same absolute `LAW_SESSION_FILES_ROOT` / `PUBLIC_UPLOAD_ROOT` for Harness and the public gateway.

Session directories are retained until an operator removes them according to the deployment's retention policy; the plugin does not silently delete customer material.
