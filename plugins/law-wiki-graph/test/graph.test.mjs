import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { buildWikiGraph } from "../lib/index.js";

async function fixture() {
  const root = await mkdtemp(path.join(os.tmpdir(), "law-wiki-graph-"));
  await mkdir(path.join(root, "cangjie_skills"));
  await mkdir(path.join(root, "llm_wiki_知识库"));
  await writeFile(path.join(root, "cangjie_skills", "labour.md"), "# 劳动关系识别\n\n成果与从属性。\n");
  await writeFile(path.join(root, "llm_wiki_知识库", "index.md"), "# 检索入口\n\n[`劳动`](../cangjie_skills/labour.md)\n");
  return root;
}

function events(pathname, callId = "call-1", failed = false) {
  return [
    { type: "tool/call", data: { callId, name: "mcp__law_wiki__read_page", arguments: JSON.stringify({ path: pathname }) } },
    { type: "tool/result", data: { ...(failed ? { error: { name: "Error", code: "FAILED" } } : {}), message: { source: { callId }, content: [{ type: "tool-result", isError: failed }] } } }
  ];
}

test("builds a read-only graph of every Markdown page", async () => {
  const graph = await buildWikiGraph(await fixture());
  assert.equal(graph.readonly, true);
  assert.equal(graph.stats.documents, 2);
  assert.equal(graph.nodes.filter((node) => node.type === "page").length, 2);
  assert.ok(graph.edges.some((edge) => edge.type === "references"));
});

test("highlights only successful concrete Wiki reads and accumulates repeats", async () => {
  const root = await fixture();
  const history = [
    ...events("cangjie_skills/labour.md", "call-1"),
    ...events("cangjie_skills/labour.md", "call-2"),
    ...events("llm_wiki_知识库/index.md", "failed", true),
    { type: "tool/call", data: { callId: "search", name: "mcp__law_wiki__search", arguments: "{\"query\":\"劳动\"}" } }
  ];
  const graph = await buildWikiGraph(root, history);
  const used = graph.nodes.find((node) => node.path === "cangjie_skills/labour.md");
  assert.equal(used.usage, 2);
  assert.equal(graph.stats.totalReads, 2);
  assert.equal(graph.stats.usedDocuments, 1);
  assert.equal(graph.nodes.find((node) => node.path === "llm_wiki_知识库/index.md").usage, 0);
  assert.equal(graph.edges.find((edge) => edge.target === used.id && edge.type === "contains").usage, 2);
});

test("ignores unknown paths and invalid arguments", async () => {
  const root = await fixture();
  const graph = await buildWikiGraph(root, [
    ...events("../secret.md", "escape"),
    { type: "tool/call", data: { callId: "bad", name: "mcp__law_wiki__read_page", arguments: "{" } },
    { type: "tool/result", data: { message: { source: { callId: "bad" }, content: [] } } }
  ]);
  assert.equal(graph.stats.totalReads, 0);
});

test("reads OKF frontmatter, source relationships, and native concept reads", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "law-okf-graph-"));
  await mkdir(path.join(root, "sources"));
  await mkdir(path.join(root, "playbooks"));
  await writeFile(path.join(root, "index.md"), '---\nokf_version: "0.2"\n---\n\n# OKF\n');
  await writeFile(path.join(root, "sources", "register.md"), '---\ntitle: Register\ntype: Source Register\nstatus: stable\n---\n\n# Register\n');
  await writeFile(path.join(root, "playbooks", "privacy.md"), '---\ntitle: Privacy router\ntype: Legal Playbook\ndescription: Privacy routing\nstatus: draft\ntags: ["privacy", "EU"]\nlaw:\n  jurisdictions: ["EU"]\nsources:\n  - id: register\n    resource: /sources/register.md\n---\n\n# Privacy router\n\n[Register](/sources/register.md)\n');
  const graph = await buildWikiGraph(root, [
    { type: "tool/call", data: { callId: "native", name: "mcp__law_wiki__okf_read_concept", arguments: JSON.stringify({ concept_id: "playbooks/privacy" }) } },
    { type: "tool/result", data: { message: { source: { callId: "native" }, content: [{ type: "tool-result" }] } } }
  ]);
  const privacy = graph.nodes.find((node) => node.conceptId === "playbooks/privacy");
  assert.equal(graph.schemaVersion, 2);
  assert.equal(privacy.conceptType, "Legal Playbook");
  assert.deepEqual(privacy.tags, ["privacy", "EU"]);
  assert.deepEqual(privacy.jurisdictions, ["EU"]);
  assert.equal(privacy.usage, 1);
  assert.ok(graph.edges.some((edge) => edge.type === "sources" && edge.source === privacy.id));
});
