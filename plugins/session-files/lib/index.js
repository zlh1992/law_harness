import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

import { defineTool } from "@deepseek-ai/dsh-tools";

import {
  listSessionFiles,
  registerLocalReference,
  resolveSessionFile,
  SESSION_ID_PATTERN
} from "./storage.js";

export const name = "session-files";
export const inject = ["webServer", "sessions", "tools", "systemPrompt"];

const LIST_ROUTE = "/api/session-files";
const LOCAL_REFERENCE_ROUTE = "/api/session-files/local-reference";
const MAX_LOCAL_REQUEST_BYTES = 32 * 1024;
const DEFAULT_READ_LINES = 300;
const MAX_READ_LINES = 1_000;
const MAX_LINE_CHARS = 5_000;
const execFileAsync = promisify(execFile);

function json(res, status, payload, headOnly = false) {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.setHeader("x-content-type-options", "nosniff");
  res.end(headOnly ? undefined : body);
}

async function readJson(req, limit = MAX_LOCAL_REQUEST_BYTES) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw Object.assign(new Error("Request body is too large"), { status: 413 });
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw Object.assign(new Error("Request body must be valid JSON"), { status: 400 });
  }
}

function requireSession(ctx, sessionId) {
  if (!SESSION_ID_PATTERN.test(String(sessionId || ""))) throw Object.assign(new Error("Invalid session id"), { status: 400 });
  if (!ctx.sessions.get(sessionId)) throw Object.assign(new Error("Session was not found"), { status: 404 });
  return sessionId;
}

function currentSessionId(exec) {
  const sessionId = exec.agent?.session?.id;
  if (!sessionId || !SESSION_ID_PATTERN.test(sessionId)) throw new Error("session_file tools require a live Harness session");
  return sessionId;
}

function positiveInteger(value, fallback, maximum, label) {
  const parsed = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > maximum) throw new Error(`${label} must be an integer from 1 to ${maximum}`);
  return parsed;
}

export function windowLines(content, offset = 1, limit = DEFAULT_READ_LINES) {
  const lines = String(content).replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
  const start = Math.min(lines.length, offset - 1);
  const selected = lines.slice(start, start + limit).map((text, index) => ({
    number: start + index + 1,
    text: text.length > MAX_LINE_CHARS ? `${text.slice(0, MAX_LINE_CHARS)}…[line truncated]` : text
  }));
  return { lines: selected, totalLines: lines.length, hasMore: start + selected.length < lines.length };
}

export async function extractDocument(extractorPython, extractorEntry, filePath, signal) {
  const { stdout } = await execFileAsync(extractorPython, [extractorEntry, filePath], {
    encoding: "utf8",
    maxBuffer: 12 * 1024 * 1024,
    timeout: 90_000,
    signal
  });
  const result = JSON.parse(stdout);
  if (!result?.ok || typeof result.content !== "string") throw new Error(result?.error || "Document extractor returned an invalid response");
  return result;
}

function applyRoutes(ctx, root) {
  ctx.effect(() => ctx.webServer.register({
    kind: "exact",
    path: LIST_ROUTE,
    async handler(req, res) {
      const method = req.method || "GET";
      if (method !== "GET" && method !== "HEAD") {
        res.setHeader("allow", "GET, HEAD");
        return json(res, 405, { error: "method_not_allowed" }, method === "HEAD");
      }
      try {
        const requestUrl = new URL(req.url || LIST_ROUTE, "http://dsh.internal");
        const sessionId = requireSession(ctx, requestUrl.searchParams.get("sessionId") || "");
        if (method === "HEAD") {
          res.statusCode = 204;
          res.setHeader("cache-control", "no-store");
          return res.end();
        }
        return json(res, 200, { readonly: true, sessionId, files: await listSessionFiles(root, sessionId) });
      } catch (error) {
        return json(res, Number(error?.status) || 500, { error: error?.code || "session_files_unavailable", message: error instanceof Error ? error.message : String(error) }, method === "HEAD");
      }
    }
  }), "session-files: list session-scoped files");

  ctx.effect(() => ctx.webServer.register({
    kind: "exact",
    path: LOCAL_REFERENCE_ROUTE,
    async handler(req, res) {
      if (req.method !== "POST") {
        res.setHeader("allow", "POST");
        return json(res, 405, { error: "method_not_allowed" });
      }
      try {
        const body = await readJson(req);
        const sessionId = requireSession(ctx, body?.sessionId || "");
        const file = await registerLocalReference(root, sessionId, body?.path);
        return json(res, 201, { ok: true, file });
      } catch (error) {
        ctx.logger.warn(`session-files local reference: ${error instanceof Error ? error.message : String(error)}`);
        return json(res, Number(error?.status) || 400, { error: error?.code || "local_reference_failed", message: error instanceof Error ? error.message : String(error) });
      }
    }
  }), "session-files: register loopback local path");
}

function applyTools(ctx, root, extractorPython, extractorEntry) {
  ctx.systemPrompt.section({
    name: "tool:session-files",
    order: 115,
    text: "Files attached through the Session Files UI are isolated to the current conversation. Use session_file_list to discover their ids, then session_file_read to extract bounded text. Never claim to have read an attached file before a successful session_file_read call. Local references remain in place; public uploads are copied into this Mac's per-session workspace."
  });

  ctx.tools.register(defineTool({
    name: "session_file_list",
    description: "List files that the user attached to the current conversation. Returns session-scoped ids; it cannot enumerate other sessions or the Mac filesystem.",
    parameters: {},
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          files: {
            type: "array",
            required: true,
            items: {
              type: "object",
              additionalProperties: false,
              properties: {
                id: { type: "string", required: true },
                name: { type: "string", required: true },
                source: { type: "string", required: true },
                mediaType: { type: "string", required: true },
                bytes: { type: "integer", required: true },
                createdAt: { type: "string", required: true }
              }
            }
          }
        }
      },
      render(_args, value) {
        const text = value.files.length
          ? value.files.map((file) => `- ${file.id} · ${file.name} · ${file.source} · ${file.bytes} bytes`).join("\n")
          : "当前会话没有已登记文件。";
        return [{ type: "text", text }];
      }
    },
    isConcurrencySafe() {
      return true;
    },
    async execute(_args, exec) {
      return { files: await listSessionFiles(root, currentSessionId(exec)) };
    }
  }));

  ctx.tools.register(defineTool({
    name: "session_file_read",
    description: "Extract and read a bounded line window from one file attached to the current conversation. Supports text, PDF, Word, Excel and PowerPoint documents; use offset to continue.",
    parameters: {
      file_id: { type: "string", required: true, description: "Session-scoped file id returned by session_file_list or the upload UI." },
      offset: { type: "integer", description: "1-based first extracted text line. Defaults to 1." },
      limit: { type: "integer", description: `Maximum extracted lines, from 1 to ${MAX_READ_LINES}. Defaults to ${DEFAULT_READ_LINES}.` }
    },
    output: {
      schema: {
        type: "object",
        additionalProperties: false,
        properties: {
          id: { type: "string", required: true },
          name: { type: "string", required: true },
          source: { type: "string", required: true },
          extractor: { type: "string", required: true },
          offset: { type: "integer", required: true },
          totalLines: { type: "integer", required: true },
          hasMore: { type: "boolean", required: true },
          extractionTruncated: { type: "boolean", required: true },
          lines: {
            type: "array",
            required: true,
            items: {
              type: "object",
              additionalProperties: false,
              properties: {
                number: { type: "integer", required: true },
                text: { type: "string", required: true }
              }
            }
          }
        }
      },
      render(_args, value) {
        const header = `${value.name} (${value.source}, extractor=${value.extractor}, lines=${value.offset}-${value.lines.at(-1)?.number ?? value.offset - 1}/${value.totalLines})`;
        const body = value.lines.map((line) => `${line.number}: ${line.text}`).join("\n");
        const tail = value.hasMore ? "\n[More lines available: call session_file_read with the next offset.]" : "";
        const extractionTail = value.extractionTruncated ? "\n[Extractor output reached its safety cap; the source may contain more content.]" : "";
        return [{ type: "text", text: `${header}\n${body}${tail}${extractionTail}` }];
      }
    },
    isConcurrencySafe() {
      return true;
    },
    timeoutMs: 90_000,
    async execute(args, exec) {
      const sessionId = currentSessionId(exec);
      const offset = positiveInteger(args.offset, 1, Number.MAX_SAFE_INTEGER, "offset");
      const limit = positiveInteger(args.limit, DEFAULT_READ_LINES, MAX_READ_LINES, "limit");
      const entry = await resolveSessionFile(root, sessionId, args.file_id);
      const extracted = await extractDocument(extractorPython, extractorEntry, entry.realPath, exec.signal);
      const window = windowLines(extracted.content, offset, limit);
      return {
        id: entry.id,
        name: entry.name,
        source: entry.source,
        extractor: extracted.extractor,
        offset,
        totalLines: window.totalLines,
        hasMore: window.hasMore,
        extractionTruncated: Boolean(extracted.truncated),
        lines: window.lines
      };
    }
  }));
}

export function apply(ctx, config = {}) {
  const root = path.resolve(config.root || process.env.LAW_SESSION_FILES_ROOT || "workspaces/session-files");
  const extractorPython = path.resolve(config.extractorPython || process.env.LAW_SESSION_FILE_PYTHON || ".venv/bin/python");
  const extractorEntry = path.resolve(config.extractorEntry || process.env.LAW_SESSION_FILE_EXTRACTOR || "services/session_file_extract.py");
  applyRoutes(ctx, root);
  applyTools(ctx, root, extractorPython, extractorEntry);
}
