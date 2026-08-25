import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

export const name = "law-wiki-graph";
export const inject = ["webServer", "sessions"];

const ROUTE = "/api/law-wiki-graph";
const MAX_DOCUMENTS = 2_000;
const MAX_MARKDOWN_BYTES = 1_000_000;
const SESSION_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;
const CATEGORY_LABELS = {
  concepts: "治理与契约",
  computations: "可复现计算",
  jurisdictions: "法域覆盖",
  playbooks: "行动路由",
  sources: "来源登记",
  cangjie_skills: "法务业务知识",
  llm_wiki_知识库: "知识库导航与治理"
};

function posix(value) {
  return value.split(path.sep).join("/");
}

function conceptId(relativePath) {
  return relativePath.replace(/\.md$/i, "");
}

function pageId(relativePath) {
  return `concept:${conceptId(relativePath)}`;
}

function unquote(value) {
  const trimmed = String(value ?? "").trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) return trimmed.slice(1, -1);
  return trimmed;
}

function frontmatter(markdown) {
  const match = markdown.match(/^---\s*\n([\s\S]*?)\n---\s*(?:\n|$)/);
  const raw = match?.[1] ?? "";
  const scalar = (key) => {
    const value = raw.match(new RegExp(`^${key}:\\s*(.+?)\\s*$`, "m"))?.[1];
    return value ? unquote(value) : "";
  };
  const list = (key) => {
    const value = scalar(key);
    if (!value) return [];
    if (value.startsWith("[")) {
      try {
        const parsed = JSON.parse(value);
        return Array.isArray(parsed) ? parsed.map(String) : [];
      } catch {
        return value.slice(1, -1).split(",").map((item) => unquote(item.trim())).filter(Boolean);
      }
    }
    return [unquote(value)];
  };
  const jurisdictions = raw.match(/^\s{2}jurisdictions:\s*(.+?)\s*$/m)?.[1] ?? "";
  const verified = raw.match(/^verified:\s*\n([\s\S]*?)(?=^[A-Za-z0-9_.-]+:|$)/m)?.[1] ?? "";
  const trust = verified ? (/human:/i.test(verified) ? "human-reviewed" : "machine-confirmed") : "unverified";
  return {
    raw,
    title: scalar("title"),
    description: scalar("description"),
    conceptType: scalar("type"),
    status: scalar("status") || "stable",
    tags: list("tags"),
    jurisdictions: jurisdictions ? listFromValue(jurisdictions) : [],
    trust
  };
}

function listFromValue(value) {
  const raw = String(value ?? "").trim();
  if (raw.startsWith("[")) {
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch {
      return raw.slice(1, -1).split(",").map((item) => unquote(item.trim())).filter(Boolean);
    }
  }
  return raw ? [unquote(raw)] : [];
}

function titleFor(markdown, relativePath, metadata = frontmatter(markdown)) {
  if (metadata.title) return metadata.title;
  const body = metadata.raw ? markdown.slice(markdown.indexOf("---", 4) + 3) : markdown;
  const match = body.match(/^#\s+(.+?)\s*$/m);
  return match?.[1]?.trim() || path.posix.basename(relativePath, ".md");
}

function groupFor(relativePath) {
  const group = relativePath.includes("/") ? relativePath.split("/", 1)[0] : "root";
  return CATEGORY_LABELS[group] || (group === "root" ? "整合说明" : group);
}

function isReserved(relativePath) {
  return /(?:^|\/)(?:index|log)\.md$/i.test(relativePath);
}

async function markdownFiles(root) {
  const found = [];
  async function walk(directory) {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(absolute);
      else if (entry.isFile() && entry.name.toLowerCase().endsWith(".md")) {
        found.push(absolute);
        if (found.length > MAX_DOCUMENTS) throw new Error(`LLM Wiki exceeds ${MAX_DOCUMENTS} Markdown documents`);
      }
    }
  }
  await walk(root);
  return found;
}

function linkCandidates(markdown) {
  const values = [];
  for (const match of markdown.matchAll(/\[[^\]]*\]\(([^)#?\s]+)(?:\s+[^)]*)?\)/g)) values.push(match[1]);
  for (const match of markdown.matchAll(/(?<!\\)\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]/g)) values.push(match[1]);
  return [...new Set(values.map((value) => value.trim().replace(/^<|>$/g, "")).filter(Boolean))];
}

function sourceCandidates(metadata) {
  return [...metadata.raw.matchAll(/^\s+resource:\s*(.+?)\s*$/gm)].map((match) => unquote(match[1]));
}

function resolveWikiLink(sourcePath, rawTarget, knownPaths) {
  let decoded;
  try {
    decoded = decodeURIComponent(rawTarget).replaceAll("\\", "/");
  } catch {
    return undefined;
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(decoded) || decoded.startsWith("#")) return undefined;
  const normal = decoded.startsWith("/")
    ? path.posix.normalize(decoded.slice(1))
    : path.posix.normalize(path.posix.join(path.posix.dirname(sourcePath), decoded));
  if (!normal.startsWith("../") && knownPaths.has(normal)) return normal;
  const withExtension = normal.endsWith(".md") ? normal : `${normal}.md`;
  return !withExtension.startsWith("../") && knownPaths.has(withExtension) ? withExtension : undefined;
}

function successfulWikiReads(events, knownPaths, knownConcepts) {
  const pending = new Map();
  const usage = new Map();
  for (const event of events ?? []) {
    if (event?.type === "tool/call") {
      const data = event.data ?? {};
      const name = String(data.name ?? "");
      if (!/(?:^|__)law_wiki__(?:read_page|okf_read_concept)$/.test(name)) continue;
      try {
        const args = JSON.parse(data.arguments || "{}");
        let requested = name.endsWith("okf_read_concept") ? String(args.concept_id ?? args.id ?? "") : String(args.path ?? "");
        requested = requested.replaceAll("\\", "/").replace(/^\.\//, "").replace(/^\//, "");
        const candidate = name.endsWith("okf_read_concept") ? `${requested.replace(/\.md$/i, "")}.md` : requested;
        const normalized = path.posix.normalize(candidate);
        if (knownPaths.has(normalized) && (!name.endsWith("okf_read_concept") || knownConcepts.has(conceptId(normalized)))) pending.set(String(data.callId), normalized);
      } catch {
        // Invalid model arguments are not successful Wiki reads.
      }
      continue;
    }
    if (event?.type !== "tool/result" || event.data?.error) continue;
    const message = event.data?.message;
    const callId = String(message?.source?.callId ?? "");
    const usedPath = pending.get(callId);
    if (!usedPath) continue;
    const blocks = Array.isArray(message?.content) ? message.content : [];
    const failed = blocks.some((block) => block?.type === "tool-result" && block?.isError === true);
    if (!failed) usage.set(usedPath, (usage.get(usedPath) ?? 0) + 1);
    pending.delete(callId);
  }
  return usage;
}

export async function buildWikiGraph(root, events = []) {
  const absoluteRoot = path.resolve(root);
  const files = await markdownFiles(absoluteRoot);
  const pages = [];
  for (const absolute of files) {
    const relativePath = posix(path.relative(absoluteRoot, absolute));
    const handle = await readFile(absolute);
    if (handle.byteLength > MAX_MARKDOWN_BYTES) throw new Error(`Wiki page is too large: ${relativePath}`);
    const markdown = handle.toString("utf8");
    const metadata = frontmatter(markdown);
    pages.push({ relativePath, markdown, metadata, title: titleFor(markdown, relativePath, metadata), group: groupFor(relativePath), reserved: isReserved(relativePath) });
  }

  const knownPaths = new Set(pages.map((page) => page.relativePath));
  const knownConcepts = new Set(pages.filter((page) => !page.reserved).map((page) => conceptId(page.relativePath)));
  const usage = successfulWikiReads(events, knownPaths, knownConcepts);
  const groups = [...new Set(pages.map((page) => page.group))];
  const groupUsage = new Map(groups.map((group) => [group, 0]));
  let totalReads = 0;
  for (const page of pages) {
    const count = usage.get(page.relativePath) ?? 0;
    totalReads += count;
    groupUsage.set(page.group, (groupUsage.get(page.group) ?? 0) + count);
  }

  const nodes = [
    { id: "wiki:root", type: "root", label: "本地法务 OKF Wiki", usage: totalReads },
    ...groups.map((group) => ({ id: `group:${group}`, type: "group", label: group, usage: groupUsage.get(group) ?? 0 })),
    ...pages.map((page) => ({
      id: pageId(page.relativePath), type: "page", kind: page.reserved ? "reserved" : "concept", label: page.title,
      path: page.relativePath, conceptId: conceptId(page.relativePath), group: page.group, usage: usage.get(page.relativePath) ?? 0,
      conceptType: page.metadata.conceptType, status: page.metadata.status, trust: page.metadata.trust,
      tags: page.metadata.tags, jurisdictions: page.metadata.jurisdictions, description: page.metadata.description,
      sourceResources: sourceCandidates(page.metadata)
    }))
  ];
  const edges = [];
  for (const group of groups) edges.push({ id: `contains:root:${group}`, source: "wiki:root", target: `group:${group}`, type: "contains", usage: groupUsage.get(group) ?? 0 });
  for (const page of pages) edges.push({ id: `contains:${page.relativePath}`, source: `group:${page.group}`, target: pageId(page.relativePath), type: "contains", usage: usage.get(page.relativePath) ?? 0 });

  const edgeKeys = new Set(edges.map((edge) => `${edge.source}\u0000${edge.target}`));
  for (const page of pages) {
    const edgeTargets = [
      ...linkCandidates(page.markdown).map((target) => ["references", target]),
      ...sourceCandidates(page.metadata).map((target) => ["sources", target])
    ];
    for (const [type, rawTarget] of edgeTargets) {
      const targetPath = resolveWikiLink(page.relativePath, rawTarget, knownPaths);
      if (!targetPath || targetPath === page.relativePath) continue;
      const source = pageId(page.relativePath);
      const target = pageId(targetPath);
      const key = `${source}\u0000${target}\u0000${type}`;
      if (edgeKeys.has(key)) continue;
      edgeKeys.add(key);
      const count = Math.min(usage.get(page.relativePath) ?? 0, usage.get(targetPath) ?? 0);
      edges.push({ id: `${type}:${page.relativePath}:${targetPath}`, source, target, type, usage: count });
    }
  }

  return {
    schemaVersion: 2,
    readonly: true,
    nodes,
    edges,
    stats: {
      documents: pages.length, concepts: knownConcepts.size, groups: groups.length, edges: edges.length,
      usedDocuments: [...usage.values()].filter((count) => count > 0).length, totalReads
    }
  };
}

function json(res, status, payload, headOnly = false) {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.setHeader("x-content-type-options", "nosniff");
  res.end(headOnly ? undefined : body);
}

export function apply(ctx, config = {}) {
  const root = path.resolve(config.root || process.env.LAW_WIKI_ROOT || "knowledge/legal_okf");
  ctx.effect(() => ctx.webServer.register({
    kind: "exact",
    path: ROUTE,
    async handler(req, res) {
      const method = req.method || "GET";
      if (method !== "GET" && method !== "HEAD") {
        res.setHeader("allow", "GET, HEAD");
        return json(res, 405, { error: "method_not_allowed" }, method === "HEAD");
      }
      try {
        const requestUrl = new URL(req.url || ROUTE, "http://dsh.internal");
        const sessionId = requestUrl.searchParams.get("sessionId") || "";
        if (sessionId && !SESSION_ID.test(sessionId)) return json(res, 400, { error: "invalid_session_id" }, method === "HEAD");
        const session = sessionId ? ctx.sessions.get(sessionId) : undefined;
        const graph = await buildWikiGraph(root, session?.events ?? []);
        return json(res, 200, { ...graph, sessionId: sessionId || null }, method === "HEAD");
      } catch (error) {
        ctx.logger.warn(`law-wiki-graph: ${error instanceof Error ? error.message : String(error)}`);
        return json(res, 500, { error: "graph_unavailable" }, method === "HEAD");
      }
    }
  }), "law-wiki-graph: read-only OKF graph endpoint");
}
