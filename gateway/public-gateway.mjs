import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import http from "node:http";
import net from "node:net";
import path from "node:path";

import {
  DEFAULT_SESSION_MAX_BYTES,
  DEFAULT_UPLOAD_MAX_BYTES,
  SESSION_ID_PATTERN,
  storePublicUpload,
} from "../plugins/session-files/lib/storage.js";

const DEFAULTS = Object.freeze({
  host: "127.0.0.1",
  port: 4180,
  upstreamHost: "127.0.0.1",
  upstreamPort: 3080,
  sessionTtlSeconds: 12 * 60 * 60,
  cookieSecure: true,
  maxLoginBodyBytes: 8 * 1024,
  publicUploadMaxBytes: DEFAULT_UPLOAD_MAX_BYTES,
  publicUploadSessionMaxBytes: DEFAULT_SESSION_MAX_BYTES,
  loginAttempts: 5,
  loginWindowMs: 15 * 60 * 1000,
  publicModelProvider: "openai",
  publicModelId: "gpt-5.6-sol",
  publicModelReasoningEfforts: ["low", "medium", "high", "xhigh", "max"],
});

// The public web UI only needs to select the pre-registered law workspace and
// create/chat in sessions.  Never let a remote browser enumerate host paths,
// register a new workspace, alter Harness settings, or touch credentials.
const RESTRICTED_PUBLIC_API_PATHS = new Set([
  "/api/host.pickDirectory",
  "/api/host.listDirectory",
  "/api/host.createDirectory",
  "/api/host.openPath",
  "/api/workspace.create",
  "/api/workspace.rename",
  "/api/workspace.delete",
  "/api/workspace.insertBefore",
  "/api/workspace.insertSessionBefore",
  "/api/workspace.archiveSession",
  "/api/settings.update",
  "/api/settings.replace",
  "/api/settings.mutate",
  "/api/credentials.set",
  "/api/credentials.unset",
  "/api/agentPreset.copy",
  "/api/agentPreset.remove",
  "/api/agentPreset.openDocument",
  "/api/agentPreset.select",
  "/api/session-files/local-reference",
]);

export function configFromEnv(env = process.env) {
  return {
    host: env.PUBLIC_GATEWAY_HOST || DEFAULTS.host,
    port: Number(env.PUBLIC_GATEWAY_PORT || DEFAULTS.port),
    upstreamHost: env.HARNESS_HOST || DEFAULTS.upstreamHost,
    upstreamPort: Number(env.HARNESS_PORT || DEFAULTS.upstreamPort),
    password: env.PUBLIC_ACCESS_PASSWORD || "",
    sessionSecret: env.PUBLIC_SESSION_SECRET || env.PUBLIC_ACCESS_PASSWORD || "",
    publicWorkspaceId: env.PUBLIC_WORKSPACE_ID || "",
    lawAgentPreset: "law-assistant",
    publicModelProvider: env.PUBLIC_MODEL_PROVIDER || DEFAULTS.publicModelProvider,
    publicModelId: env.PUBLIC_MODEL_ID || env.CODEX_MODEL || DEFAULTS.publicModelId,
    publicModelReasoningEfforts: String(env.PUBLIC_MODEL_REASONING_EFFORTS || DEFAULTS.publicModelReasoningEfforts.join(","))
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean),
    sessionTtlSeconds: Number(env.PUBLIC_SESSION_TTL_SECONDS || DEFAULTS.sessionTtlSeconds),
    cookieSecure: String(env.PUBLIC_COOKIE_SECURE ?? DEFAULTS.cookieSecure).toLowerCase() !== "false",
    maxLoginBodyBytes: Number(env.PUBLIC_MAX_LOGIN_BODY_BYTES || DEFAULTS.maxLoginBodyBytes),
    publicUploadRoot: path.resolve(env.PUBLIC_UPLOAD_ROOT || env.LAW_SESSION_FILES_ROOT || "workspaces/session-files"),
    publicUploadMaxBytes: Number(env.PUBLIC_UPLOAD_MAX_BYTES || DEFAULTS.publicUploadMaxBytes),
    publicUploadSessionMaxBytes: Number(env.PUBLIC_UPLOAD_SESSION_MAX_BYTES || DEFAULTS.publicUploadSessionMaxBytes),
    loginAttempts: Number(env.PUBLIC_LOGIN_ATTEMPTS || DEFAULTS.loginAttempts),
    loginWindowMs: Number(env.PUBLIC_LOGIN_WINDOW_MS || DEFAULTS.loginWindowMs),
  };
}

function parseCookies(value = "") {
  return Object.fromEntries(value.split(";").map((part) => {
    const separator = part.indexOf("=");
    return separator < 0 ? ["", ""] : [part.slice(0, separator).trim(), decodeURIComponent(part.slice(separator + 1).trim())];
  }).filter(([key]) => key));
}

function constantTimeEqual(actual, expected) {
  const a = Buffer.from(String(actual));
  const b = Buffer.from(String(expected));
  return a.length === b.length && timingSafeEqual(a, b);
}

function signature(payload, secret) {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

function issueSession(config) {
  const payload = `${Math.floor(Date.now() / 1000) + config.sessionTtlSeconds}.${randomBytes(18).toString("base64url")}`;
  return `${payload}.${signature(payload, config.sessionSecret)}`;
}

function sessionValid(req, config) {
  const token = parseCookies(req.headers.cookie).law_harness_session || "";
  const last = token.lastIndexOf(".");
  if (last < 1 || !constantTimeEqual(token.slice(last + 1), signature(token.slice(0, last), config.sessionSecret))) return false;
  const expiry = Number(token.slice(0, token.indexOf(".")));
  return Number.isInteger(expiry) && expiry >= Math.floor(Date.now() / 1000);
}

function clientIp(req) {
  const forwarded = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
  return forwarded || req.socket.remoteAddress || "unknown";
}

function html(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character]);
}

function send(res, status, body, headers = {}) {
  res.writeHead(status, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer", ...headers });
  res.end(body);
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": String(Buffer.byteLength(body)),
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  res.end(body);
}

function loginPage(error = "") {
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>法务助手访问</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#10131a;color:#e8edf7;display:grid;place-items:center;min-height:100vh;margin:0}.card{max-width:440px;padding:32px;border:1px solid #303a4c;border-radius:14px;background:#181d27}input,button{width:100%;box-sizing:border-box;padding:12px;margin:9px 0;border-radius:8px}input{background:#0f1420;border:1px solid #455269;color:#fff}button{background:#5b8cff;border:0;color:#fff;font-weight:600}.warn{color:#ffbd72;line-height:1.55}.error{color:#ff8989}</style><main class="card"><h1>法务助手</h1><p class="warn">仅限授权用户。不要上传身份证号、完整合同、商业秘密或未脱敏个人信息；输出仅供法务风险分流，不构成正式法律意见。</p>${error ? `<p class="error">${html(error)}</p>` : ""}<form method="post" action="/login"><label>访问口令<input name="password" type="password" autocomplete="current-password" required autofocus></label><button type="submit">进入 DeepSeek Harness</button></form></main></html>`;
}

async function readForm(req, limit) {
  const body = await readRaw(req, limit);
  return new URLSearchParams(body.toString("utf8"));
}

async function readRaw(req, limit) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw Object.assign(new Error("Request body too large"), { status: 413 });
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

function proxyHeaders(req, config) {
  const upstreamOrigin = `http://${config.upstreamHost}:${config.upstreamPort}`;
  const headers = { ...req.headers, host: `${config.upstreamHost}:${config.upstreamPort}` };
  delete headers["proxy-connection"];
  // Harness rejects browser API and WebSocket traffic when Origin and Host do
  // not describe the same trusted authority.  The public gateway has already
  // authenticated the request, so present its private loopback hop as
  // same-origin without forwarding the remote browser's trust markers.
  if (headers.origin !== undefined) headers.origin = upstreamOrigin;
  if (headers["sec-fetch-site"] !== undefined) headers["sec-fetch-site"] = "same-origin";
  headers["x-forwarded-proto"] = "https";
  headers["x-forwarded-host"] = String(req.headers.host || "");
  return headers;
}

function allowedLawSessionCreate(raw, config) {
  try {
    const message = JSON.parse(raw.toString("utf8"));
    const payload = message?.payload || {};
    return message?.type === "client-request"
      && message?.method === "session.create"
      && payload.workspaceId === config.publicWorkspaceId
      && payload.cwd === undefined
      && (payload.agentPreset === undefined || payload.agentPreset === config.lawAgentPreset);
  } catch {
    return false;
  }
}

function allowedLawModelSelection(raw, config) {
  try {
    const message = JSON.parse(raw.toString("utf8"));
    const payload = message?.payload || {};
    return message?.type === "client-request"
      && message?.method === "session.selectModel"
      && typeof payload.sessionId === "string"
      && payload.sessionId.length > 0
      && payload.provider === config.publicModelProvider
      && payload.model === config.publicModelId
      && (payload.reasoningEffort === undefined || config.publicModelReasoningEfforts.includes(payload.reasoningEffort));
  } catch {
    return false;
  }
}

function filterPublicModelCatalog(message, config) {
  const value = message?.result?.ok ? message.result.value : null;
  if (!value || !Array.isArray(value.groups)) return message;
  value.groups = value.groups
    .filter((group) => group?.id === config.publicModelProvider)
    .map((group) => ({
      ...group,
      models: Array.isArray(group.models)
        ? group.models.filter((model) => model?.id === config.publicModelId).map((model) => ({
          ...model,
          ...(model.reasoning && Array.isArray(model.reasoning.efforts)
            ? { reasoning: { ...model.reasoning, efforts: model.reasoning.efforts.filter((effort) => config.publicModelReasoningEfforts.includes(effort?.id)) } }
            : {}),
        }))
        : [],
    }))
    .filter((group) => group.models.length > 0);
  value.failures = [];
  return message;
}

function proxyToUpstream(req, res, config, body) {
  const headers = proxyHeaders(req, config);
  if (body) headers["content-length"] = String(body.length);
  const upstream = http.request({ host: config.upstreamHost, port: config.upstreamPort, method: req.method, path: req.url, headers }, (upstreamRes) => {
    res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
    upstreamRes.pipe(res);
  });
  upstream.on("error", () => {
    if (!res.headersSent) send(res, 502, loginPage("Harness 暂不可用，请稍后重试。"));
    else res.destroy();
  });
  if (body) upstream.end(body);
  else req.pipe(upstream);
}

function proxyBufferedJsonToUpstream(req, res, config, body, transform) {
  const headers = proxyHeaders(req, config);
  headers["content-length"] = String(body.length);
  const upstream = http.request({ host: config.upstreamHost, port: config.upstreamPort, method: req.method, path: req.url, headers }, (upstreamRes) => {
    const chunks = [];
    let size = 0;
    upstreamRes.on("data", (chunk) => {
      size += chunk.length;
      if (size <= 1024 * 1024) chunks.push(chunk);
    });
    upstreamRes.on("end", () => {
      if (size > 1024 * 1024) {
        send(res, 502, loginPage("Harness 返回内容异常。"));
        return;
      }
      let payload = Buffer.concat(chunks);
      try {
        payload = Buffer.from(JSON.stringify(transform(JSON.parse(payload.toString("utf8")))));
      } catch {
        // Preserve upstream errors and future-compatible response shapes.
      }
      const responseHeaders = { ...upstreamRes.headers, "content-length": String(payload.length) };
      delete responseHeaders["transfer-encoding"];
      res.writeHead(upstreamRes.statusCode || 502, responseHeaders);
      res.end(payload);
    });
  });
  upstream.on("error", () => {
    if (!res.headersSent) send(res, 502, loginPage("Harness 暂不可用，请稍后重试。"));
    else res.destroy();
  });
  upstream.end(body);
}

function upstreamSessionExists(config, sessionId) {
  return new Promise((resolve) => {
    const upstream = http.request({
      host: config.upstreamHost,
      port: config.upstreamPort,
      method: "HEAD",
      path: `/api/session-files?sessionId=${encodeURIComponent(sessionId)}`,
      headers: { host: `${config.upstreamHost}:${config.upstreamPort}` },
    }, (response) => {
      response.resume();
      resolve(response.statusCode === 204 || response.statusCode === 200);
    });
    upstream.setTimeout(5_000, () => {
      upstream.destroy();
      resolve(false);
    });
    upstream.on("error", () => resolve(false));
    upstream.end();
  });
}

export function createGateway(options = {}) {
  const config = { ...configFromEnv(), ...(options.config || {}) };
  const attempts = new Map();

  const tooManyAttempts = (ip) => {
    const cutoff = Date.now() - config.loginWindowMs;
    const list = (attempts.get(ip) || []).filter((at) => at > cutoff);
    attempts.set(ip, list);
    return list.length >= config.loginAttempts;
  };
  const recordFailure = (ip) => attempts.set(ip, [...(attempts.get(ip) || []), Date.now()]);

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    if (req.method === "GET" && url.pathname === "/healthz") {
      res.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" });
      res.end(JSON.stringify({ ok: true, upstream: `${config.upstreamHost}:${config.upstreamPort}` }));
      return;
    }
    if (req.method === "GET" && url.pathname === "/login") {
      send(res, 200, loginPage());
      return;
    }
    if (req.method === "POST" && url.pathname === "/login") {
      const ip = clientIp(req);
      if (tooManyAttempts(ip)) {
        send(res, 429, loginPage("尝试次数过多，请 15 分钟后重试。"));
        return;
      }
      try {
        const form = await readForm(req, config.maxLoginBodyBytes);
        if (!constantTimeEqual(form.get("password") || "", config.password)) {
          recordFailure(ip);
          send(res, 401, loginPage("访问口令无效。"));
          return;
        }
        attempts.delete(ip);
        const secure = config.cookieSecure ? "; Secure" : "";
        res.writeHead(303, { location: "/", "set-cookie": `law_harness_session=${encodeURIComponent(issueSession(config))}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${config.sessionTtlSeconds}${secure}`, "cache-control": "no-store" });
        res.end();
      } catch (error) {
        send(res, Number(error?.status) || 400, loginPage(error instanceof Error ? error.message : "登录请求无效。"));
      }
      return;
    }
    if (req.method === "POST" && url.pathname === "/logout") {
      res.writeHead(303, { location: "/login", "set-cookie": "law_harness_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0; Secure", "cache-control": "no-store" });
      res.end();
      return;
    }
    if (!sessionValid(req, config)) {
      res.writeHead(303, { location: "/login", "cache-control": "no-store" });
      res.end();
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/session-files/upload") {
      try {
        const sessionId = String(req.headers["x-dsh-session-id"] || "");
        const fileName = String(req.headers["x-file-name"] || "");
        if (!SESSION_ID_PATTERN.test(sessionId)) {
          sendJson(res, 400, { error: "invalid_session_id", message: "Invalid or missing conversation Session id." });
          return;
        }
        if (!(await upstreamSessionExists(config, sessionId))) {
          sendJson(res, 404, { error: "session_not_found", message: "The conversation Session is not active on this Harness." });
          return;
        }
        const declaredLength = Number(req.headers["content-length"] || 0);
        if (Number.isFinite(declaredLength) && declaredLength > config.publicUploadMaxBytes) {
          sendJson(res, 413, { error: "UPLOAD_TOO_LARGE", message: `Uploaded file exceeds ${config.publicUploadMaxBytes} bytes.` });
          return;
        }
        const body = await readRaw(req, config.publicUploadMaxBytes);
        const file = await storePublicUpload(
          config.publicUploadRoot,
          sessionId,
          fileName,
          req.headers["content-type"],
          body,
          { maxBytes: config.publicUploadMaxBytes, sessionMaxBytes: config.publicUploadSessionMaxBytes },
        );
        sendJson(res, 201, { ok: true, file });
      } catch (error) {
        sendJson(res, Number(error?.status) || 400, { error: error?.code || "upload_failed", message: error instanceof Error ? error.message : String(error) });
      }
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/session.models") {
      try {
        const raw = await readRaw(req, config.maxLoginBodyBytes);
        proxyBufferedJsonToUpstream(req, res, config, raw, (message) => filterPublicModelCatalog(message, config));
      } catch (error) {
        send(res, Number(error?.status) || 400, loginPage(error instanceof Error ? error.message : "模型目录请求无效。"));
      }
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/session.selectModel") {
      try {
        const raw = await readRaw(req, config.maxLoginBodyBytes);
        if (!allowedLawModelSelection(raw, config)) {
          send(res, 403, "<h1>模型不可用</h1><p>公网入口只允许选择已审核的法务模型与推理等级。</p>");
          return;
        }
        proxyToUpstream(req, res, config, raw);
      } catch (error) {
        send(res, Number(error?.status) || 400, loginPage(error instanceof Error ? error.message : "模型选择请求无效。"));
      }
      return;
    }
    if (req.method === "POST" && RESTRICTED_PUBLIC_API_PATHS.has(url.pathname)) {
      send(res, 403, "<h1>操作不可用</h1><p>公网法务助手不允许管理服务器目录、工作区、设置或凭据。</p>");
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/session.create") {
      try {
        const raw = await readRaw(req, config.maxLoginBodyBytes);
        if (!allowedLawSessionCreate(raw, config)) {
          send(res, 403, "<h1>操作不可用</h1><p>公网入口只能在预注册的法务工作区创建 law-assistant 会话。</p>");
          return;
        }
        proxyToUpstream(req, res, config, raw);
      } catch (error) {
        send(res, Number(error?.status) || 400, loginPage(error instanceof Error ? error.message : "会话请求无效。"));
      }
      return;
    }

    proxyToUpstream(req, res, config);
  });

  server.on("upgrade", (req, socket, head) => {
    if (!sessionValid(req, config)) {
      socket.write("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n");
      socket.destroy();
      return;
    }
    const upstream = net.connect(config.upstreamPort, config.upstreamHost);
    upstream.on("connect", () => {
      const headers = proxyHeaders(req, config);
      const request = [`${req.method} ${req.url} HTTP/${req.httpVersion}`];
      for (const [key, value] of Object.entries(headers)) request.push(`${key}: ${Array.isArray(value) ? value.join(", ") : value}`);
      upstream.write(`${request.join("\r\n")}\r\n\r\n`);
      if (head.length) upstream.write(head);
      socket.pipe(upstream).pipe(socket);
    });
    upstream.on("error", () => socket.destroy());
  });
  return server;
}

export async function startGateway(config = configFromEnv()) {
  if (!config.password || config.password.includes("请替换")) throw new Error("PUBLIC_ACCESS_PASSWORD is not configured");
  if (!config.publicWorkspaceId || config.publicWorkspaceId.includes("请填入")) throw new Error("PUBLIC_WORKSPACE_ID is not configured");
  if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535) throw new Error("Invalid PUBLIC_GATEWAY_PORT");
  const server = createGateway({ config });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(config.port, config.host, resolve);
  });
  process.stdout.write(`Public gateway listening on http://${config.host}:${config.port} -> ${config.upstreamHost}:${config.upstreamPort}\n`);
  return server;
}

if (import.meta.url === new URL(process.argv[1], "file:").href) {
  startGateway().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
