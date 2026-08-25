import assert from "node:assert/strict";
import test from "node:test";
import { createProxyServer, parseCodexJsonl } from "../proxy.mjs";

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

function fakeResult(decision) {
  return {
    decision,
    usage: { input_tokens: 12, output_tokens: 5 },
    threadId: "thread_test",
  };
}

function config() {
  return {
    host: "127.0.0.1",
    port: 0,
    model: "gpt-5.6-sol",
    proxyToken: "local-secret",
    codexBin: "codex",
    codexCwd: "/tmp",
    outputSchemaPath: "/tmp/schema.json",
    instructionsPath: "/tmp/instructions.md",
    timeoutMs: 1000,
    maxBodyBytes: 1024 * 1024,
    maxConcurrency: 1,
  };
}

test("auth, models, normal completion, and Chat Completions SSE", async (t) => {
  const seen = [];
  const proxy = createProxyServer({
    config: config(),
    runCodex: async (request) => {
      seen.push(request);
      return fakeResult({ type: "message", content: "订阅回复正常", tool_calls: [] });
    },
  });
  const port = await listen(proxy);
  t.after(() => close(proxy));
  const base = `http://127.0.0.1:${port}`;

  const health = await fetch(`${base}/healthz`).then((response) => response.json());
  assert.equal(health.backend, "codex-cli-chatgpt-subscription");
  assert.equal(health.platformApiKeyRequired, false);
  assert.equal((await fetch(`${base}/v1/models`)).status, 401);

  const headers = { authorization: "Bearer local-secret", "content-type": "application/json" };
  const models = await fetch(`${base}/v1/models`, { headers }).then((response) => response.json());
  assert.equal(models.data[0].id, "gpt-5.6-sol");

  const normalResponse = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({ model: "anything", messages: [{ role: "user", content: "你好" }] }),
  });
  assert.equal(normalResponse.status, 200);
  const normal = await normalResponse.json();
  assert.equal(normal.model, "gpt-5.6-sol");
  assert.equal(normal.choices[0].message.content, "订阅回复正常");
  assert.equal(normal.usage.total_tokens, 17);
  assert.equal(seen[0].endpoint, "chat.completions");

  const streamResponse = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      stream: true,
      stream_options: { include_usage: true },
      messages: [{ role: "user", content: "继续" }],
    }),
  });
  assert.match(streamResponse.headers.get("content-type"), /text\/event-stream/);
  const streamText = await streamResponse.text();
  assert.match(streamText, /订阅回复正常/);
  assert.match(streamText, /"usage"/);
  assert.match(streamText, /data: \[DONE\]/);
});

test("tool calls are emitted in OpenAI format and Responses JSON/SSE work", async (t) => {
  const proxy = createProxyServer({
    config: config(),
    runCodex: async ({ endpoint, body }) => endpoint === "responses"
      ? body.input === "call a tool"
        ? fakeResult({
            type: "tool_calls",
            content: null,
            tool_calls: [{ name: "read_file", arguments: "{\"path\":\"stream.md\"}" }],
          })
        : fakeResult({ type: "message", content: "response ok", tool_calls: [] })
      : fakeResult({
          type: "tool_calls",
          content: null,
          tool_calls: [{ name: "read_file", arguments: "{\"path\":\"notes.md\"}" }],
        }),
  });
  const port = await listen(proxy);
  t.after(() => close(proxy));
  const base = `http://127.0.0.1:${port}`;
  const headers = { authorization: "Bearer local-secret", "content-type": "application/json" };

  const toolResponse = await fetch(`${base}/v1/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      messages: [{ role: "user", content: "读文件" }],
      tools: [{
        type: "function",
        function: {
          name: "read_file",
          description: "read",
          parameters: { type: "object", properties: { path: { type: "string" } } },
        },
      }],
    }),
  }).then((response) => response.json());
  assert.equal(toolResponse.choices[0].finish_reason, "tool_calls");
  assert.equal(toolResponse.choices[0].message.tool_calls[0].function.name, "read_file");
  assert.equal(toolResponse.choices[0].message.tool_calls[0].function.arguments, "{\"path\":\"notes.md\"}");

  const response = await fetch(`${base}/v1/responses`, {
    method: "POST",
    headers,
    body: JSON.stringify({ input: "hello" }),
  }).then((result) => result.json());
  assert.equal(response.object, "response");
  assert.equal(response.output_text, "response ok");

  const streamResponse = await fetch(`${base}/v1/responses`, {
    method: "POST",
    headers,
    body: JSON.stringify({ input: "hello", stream: true }),
  });
  assert.equal(streamResponse.status, 200);
  assert.match(streamResponse.headers.get("content-type"), /text\/event-stream/);
  const streamText = await streamResponse.text();
  assert.match(streamText, /"type":"response.created"/);
  assert.match(streamText, /"type":"response.output_item.added"/);
  assert.match(streamText, /"type":"response.output_text.delta"/);
  assert.match(streamText, /"type":"response.output_item.done"/);
  assert.match(streamText, /"type":"response.completed"/);
  assert.match(streamText, /response ok/);

  const toolStream = await fetch(`${base}/v1/responses`, {
    method: "POST",
    headers,
    body: JSON.stringify({ input: "call a tool", stream: true }),
  }).then((result) => result.text());
  assert.match(toolStream, /"type":"response.function_call_arguments.delta"/);
  assert.match(toolStream, /"type":"response.function_call_arguments.done"/);
  assert.match(toolStream, /\\"path\\":\\"stream.md\\"/);
});

test("Codex JSONL parsing validates tool names and arguments", () => {
  const stdout = [
    JSON.stringify({ type: "thread.started", thread_id: "t1" }),
    JSON.stringify({
      type: "item.completed",
      item: {
        type: "agent_message",
        text: JSON.stringify({
          type: "tool_calls",
          content: null,
          tool_calls: [{ name: "shell", arguments_json: "{\"cmd\":\"pwd\"}" }],
        }),
      },
    }),
    JSON.stringify({ type: "turn.completed", usage: { input_tokens: 1, output_tokens: 2 } }),
  ].join("\n");

  const result = parseCodexJsonl(stdout, ["shell"]);
  assert.equal(result.threadId, "t1");
  assert.equal(result.decision.tool_calls[0].arguments, "{\"cmd\":\"pwd\"}");
  assert.throws(() => parseCodexJsonl(stdout, ["other"]), /unavailable client tool/);
});
