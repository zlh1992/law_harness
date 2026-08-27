import assert from "node:assert/strict";
import { mkdtemp, realpath, rm } from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { createGateway } from "../public-gateway.mjs";
import { listSessionFiles, resolveSessionFile } from "../../plugins/session-files/lib/storage.js";

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server.address().port;
}

async function close(server) {
  await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
}

function envelope(method, payload) {
  return { type: "client-request", rpcId: crypto.randomUUID(), method, payload };
}

test("public model catalog is filtered and selection is allowlisted", async (t) => {
  const upstream = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const request = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    const result = request.method === "session.models"
      ? {
          ok: true,
          value: {
            current: { provider: "deepseek", model: "deepseek-v4-flash" },
            routable: true,
            groups: [
              { id: "cloud-model", name: "Cloud", models: [{ id: "remote-model", name: "Remote" }] },
              {
                id: "deepseek",
                name: "Local DeepSeek DS4F",
                models: [
                  { id: "deepseek-v4-pro", name: "Compatibility alias" },
                  { id: "deepseek-v4-flash", name: "DeepSeek V4 Flash" },
                ],
              },
            ],
            failures: [{ id: "unused", name: "unused", message: "unused" }],
          },
        }
      : { ok: true, value: { selected: request.payload } };
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ type: "server-response", rpcId: request.rpcId, result }));
  });
  const upstreamPort = await listen(upstream);
  t.after(() => close(upstream));

  const gateway = createGateway({
    config: {
      host: "127.0.0.1",
      port: 0,
      upstreamHost: "127.0.0.1",
      upstreamPort,
      password: "test-password",
      sessionSecret: "test-secret",
      publicWorkspaceId: "workspace-1",
      lawAgentPreset: "law-assistant",
      publicModelProvider: "deepseek",
      publicModelId: "deepseek-v4-flash",
      publicModelReasoningEfforts: ["high", "max"],
      sessionTtlSeconds: 3600,
      cookieSecure: false,
      maxLoginBodyBytes: 8192,
      loginAttempts: 5,
      loginWindowMs: 60_000,
    },
  });
  const port = await listen(gateway);
  t.after(() => close(gateway));
  const base = `http://127.0.0.1:${port}`;

  const login = await fetch(`${base}/login`, {
    method: "POST",
    redirect: "manual",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ password: "test-password" }),
  });
  assert.equal(login.status, 303);
  const cookie = login.headers.get("set-cookie").split(";", 1)[0];
  const headers = { cookie, "content-type": "application/json" };

  const models = await fetch(`${base}/api/session.models`, {
    method: "POST",
    headers,
    body: JSON.stringify(envelope("session.models", { sessionId: "session-1" })),
  }).then((response) => response.json());
  assert.deepEqual(models.result.value.groups.map((group) => group.id), ["deepseek"]);
  assert.deepEqual(models.result.value.groups[0].models.map((model) => model.id), ["deepseek-v4-flash"]);
  assert.deepEqual(models.result.value.failures, []);

  const allowed = await fetch(`${base}/api/session.selectModel`, {
    method: "POST",
    headers,
    body: JSON.stringify(envelope("session.selectModel", {
      sessionId: "session-1",
      provider: "deepseek",
      model: "deepseek-v4-flash",
      reasoningEffort: "high",
    })),
  });
  assert.equal(allowed.status, 200);

  const denied = await fetch(`${base}/api/session.selectModel`, {
    method: "POST",
    headers,
    body: JSON.stringify(envelope("session.selectModel", {
      sessionId: "session-1",
      provider: "cloud-model",
      model: "remote-model",
    })),
  });
  assert.equal(denied.status, 403);
});

test("authenticated public uploads land in the active conversation workspace", async (t) => {
  const uploadRoot = await mkdtemp(path.join(os.tmpdir(), "law-public-upload-"));
  t.after(() => rm(uploadRoot, { recursive: true, force: true }));
  const upstream = http.createServer((req, res) => {
    if (req.method === "HEAD" && req.url === "/api/session-files?sessionId=session-upload") {
      res.writeHead(204);
      res.end();
      return;
    }
    res.writeHead(404);
    res.end();
  });
  const upstreamPort = await listen(upstream);
  t.after(() => close(upstream));
  const gateway = createGateway({ config: {
    host: "127.0.0.1",
    port: 0,
    upstreamHost: "127.0.0.1",
    upstreamPort,
    password: "test-password",
    sessionSecret: "test-secret",
    publicWorkspaceId: "workspace-1",
    lawAgentPreset: "law-assistant",
    publicModelProvider: "deepseek",
    publicModelId: "deepseek-v4-flash",
    publicModelReasoningEfforts: ["high", "max"],
    sessionTtlSeconds: 3600,
    cookieSecure: false,
    maxLoginBodyBytes: 8192,
    publicUploadRoot: uploadRoot,
    publicUploadMaxBytes: 1024,
    publicUploadSessionMaxBytes: 4096,
    loginAttempts: 5,
    loginWindowMs: 60_000,
  } });
  const port = await listen(gateway);
  t.after(() => close(gateway));
  const base = `http://127.0.0.1:${port}`;
  const login = await fetch(`${base}/login`, {
    method: "POST",
    redirect: "manual",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ password: "test-password" }),
  });
  const cookie = login.headers.get("set-cookie").split(";", 1)[0];

  const upload = await fetch(`${base}/api/session-files/upload`, {
    method: "POST",
    headers: {
      cookie,
      "content-type": "text/plain",
      "x-dsh-session-id": "session-upload",
      "x-file-name": encodeURIComponent("客户材料.txt"),
    },
    body: "only this session",
  });
  assert.equal(upload.status, 201);
  const payload = await upload.json();
  assert.equal(payload.file.source, "public-upload");
  const records = await listSessionFiles(uploadRoot, "session-upload");
  assert.equal(records.length, 1);
  const resolved = await resolveSessionFile(uploadRoot, "session-upload", payload.file.id);
  assert.ok(resolved.realPath.startsWith(path.join(await realpath(uploadRoot), "session-upload", "uploads") + path.sep));

  const deniedLocalPath = await fetch(`${base}/api/session-files/local-reference`, {
    method: "POST",
    headers: { cookie, "content-type": "application/json" },
    body: JSON.stringify({ sessionId: "session-upload", path: "/etc/hosts" }),
  });
  assert.equal(deniedLocalPath.status, 403);

  const deniedType = await fetch(`${base}/api/session-files/upload`, {
    method: "POST",
    headers: { cookie, "x-dsh-session-id": "session-upload", "x-file-name": "payload.sh" },
    body: "echo unsafe",
  });
  assert.equal(deniedType.status, 415);
});
