import { createHash, randomBytes, randomUUID } from "node:crypto";
import { mkdir, open, readFile, readdir, realpath, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";

export const SESSION_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;
export const FILE_ID_PATTERN = /^[a-f0-9-]{36}$/;
export const DEFAULT_UPLOAD_MAX_BYTES = 25 * 1024 * 1024;
export const DEFAULT_SESSION_MAX_BYTES = 250 * 1024 * 1024;

const ALLOWED_PUBLIC_EXTENSIONS = new Set([
  ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
  ".xml", ".html", ".htm", ".log", ".pdf", ".doc", ".docx", ".rtf", ".odt",
  ".xlsx", ".pptx"
]);

function assertSessionId(sessionId) {
  if (!SESSION_ID_PATTERN.test(String(sessionId || ""))) throw Object.assign(new Error("Invalid session id"), { code: "INVALID_SESSION_ID", status: 400 });
  return String(sessionId);
}

function assertFileId(fileId) {
  if (!FILE_ID_PATTERN.test(String(fileId || ""))) throw Object.assign(new Error("Invalid file id"), { code: "INVALID_FILE_ID", status: 400 });
  return String(fileId);
}

function inside(root, target) {
  const relative = path.relative(root, target);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

export function sessionDirectory(root, sessionId) {
  const absoluteRoot = path.resolve(root);
  const target = path.resolve(absoluteRoot, assertSessionId(sessionId));
  if (!inside(absoluteRoot, target)) throw Object.assign(new Error("Session directory escapes storage root"), { code: "PATH_ESCAPE", status: 400 });
  return target;
}

function recordDirectory(root, sessionId) {
  return path.join(sessionDirectory(root, sessionId), "records");
}

function publicView(entry) {
  return {
    id: entry.id,
    name: entry.name,
    source: entry.source,
    mediaType: entry.mediaType,
    bytes: entry.bytes,
    createdAt: entry.createdAt
  };
}

export function sanitizeUploadName(rawName) {
  let decoded;
  try {
    decoded = decodeURIComponent(String(rawName || ""));
  } catch {
    throw Object.assign(new Error("Invalid encoded file name"), { code: "INVALID_FILE_NAME", status: 400 });
  }
  const basename = path.basename(decoded.replaceAll("\\", "/")).normalize("NFKC");
  const cleaned = basename.replace(/[\u0000-\u001f\u007f/:\\]/g, "_").replace(/\s+/g, " ").trim();
  if (!cleaned || cleaned === "." || cleaned === "..") throw Object.assign(new Error("File name is empty"), { code: "INVALID_FILE_NAME", status: 400 });
  const extension = path.extname(cleaned).toLowerCase();
  if (!ALLOWED_PUBLIC_EXTENSIONS.has(extension)) {
    throw Object.assign(new Error(`Public upload type is not allowed: ${extension || "no extension"}`), { code: "UPLOAD_TYPE_DENIED", status: 415 });
  }
  const extensionBytes = Buffer.byteLength(extension);
  const maxStemBytes = Math.max(20, 180 - extensionBytes);
  let stem = path.basename(cleaned, extension);
  while (Buffer.byteLength(stem) > maxStemBytes) stem = stem.slice(0, -1);
  return `${stem || "file"}${extension}`;
}

async function atomicRecord(root, entry) {
  const records = recordDirectory(root, entry.sessionId);
  await mkdir(records, { recursive: true, mode: 0o700 });
  const target = path.join(records, `${entry.id}.json`);
  const temporary = path.join(records, `.${entry.id}.${randomBytes(5).toString("hex")}.tmp`);
  await writeFile(temporary, `${JSON.stringify(entry)}\n`, { encoding: "utf8", mode: 0o600, flag: "wx" });
  await rename(temporary, target);
}

async function loadRecord(root, sessionId, fileId) {
  const target = path.join(recordDirectory(root, assertSessionId(sessionId)), `${assertFileId(fileId)}.json`);
  let entry;
  try {
    entry = JSON.parse(await readFile(target, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") throw Object.assign(new Error("Session file was not found"), { code: "SESSION_FILE_NOT_FOUND", status: 404 });
    throw error;
  }
  if (entry?.schemaVersion !== 1 || entry.sessionId !== sessionId || entry.id !== fileId || !["local-reference", "public-upload"].includes(entry.source)) {
    throw Object.assign(new Error("Session file record is invalid"), { code: "SESSION_FILE_RECORD_INVALID", status: 500 });
  }
  return entry;
}

export async function listSessionFiles(root, sessionId) {
  const directory = recordDirectory(root, assertSessionId(sessionId));
  let names;
  try {
    names = await readdir(directory);
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  const entries = [];
  for (const name of names.sort()) {
    if (!/^[a-f0-9-]{36}\.json$/.test(name)) continue;
    try {
      const entry = JSON.parse(await readFile(path.join(directory, name), "utf8"));
      if (entry?.schemaVersion === 1 && entry.sessionId === sessionId && entry.id === name.slice(0, -5)) entries.push(entry);
    } catch {
      // One damaged record must not hide the rest of the session's files.
    }
  }
  entries.sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  return entries.map(publicView);
}

export async function registerLocalReference(root, sessionId, requestedPath) {
  assertSessionId(sessionId);
  if (!path.isAbsolute(String(requestedPath || ""))) throw Object.assign(new Error("Local file path must be absolute"), { code: "LOCAL_PATH_NOT_ABSOLUTE", status: 400 });
  const resolved = await realpath(String(requestedPath));
  const info = await stat(resolved);
  if (!info.isFile()) throw Object.assign(new Error("Local path is not a regular file"), { code: "LOCAL_PATH_NOT_FILE", status: 400 });
  const entry = {
    schemaVersion: 1,
    id: randomUUID(),
    sessionId,
    name: path.basename(resolved),
    source: "local-reference",
    mediaType: "application/octet-stream",
    bytes: info.size,
    createdAt: new Date().toISOString(),
    realPath: resolved
  };
  await atomicRecord(root, entry);
  return publicView(entry);
}

export async function storePublicUpload(root, sessionId, rawName, mediaType, data, options = {}) {
  assertSessionId(sessionId);
  if (!Buffer.isBuffer(data)) throw Object.assign(new Error("Upload body must be bytes"), { code: "INVALID_UPLOAD_BODY", status: 400 });
  const maxBytes = Number(options.maxBytes ?? DEFAULT_UPLOAD_MAX_BYTES);
  const sessionMaxBytes = Number(options.sessionMaxBytes ?? DEFAULT_SESSION_MAX_BYTES);
  if (data.byteLength < 1) throw Object.assign(new Error("Uploaded file is empty"), { code: "EMPTY_UPLOAD", status: 400 });
  if (data.byteLength > maxBytes) throw Object.assign(new Error(`Uploaded file exceeds ${maxBytes} bytes`), { code: "UPLOAD_TOO_LARGE", status: 413 });
  const existing = await listSessionFiles(root, sessionId);
  const publicBytes = existing.filter((entry) => entry.source === "public-upload").reduce((sum, entry) => sum + entry.bytes, 0);
  if (publicBytes + data.byteLength > sessionMaxBytes) throw Object.assign(new Error(`Session upload quota exceeds ${sessionMaxBytes} bytes`), { code: "SESSION_UPLOAD_QUOTA", status: 413 });

  const safeName = sanitizeUploadName(rawName);
  const sessionRoot = sessionDirectory(root, sessionId);
  const uploads = path.join(sessionRoot, "uploads");
  await mkdir(uploads, { recursive: true, mode: 0o700 });
  const storedName = `${Date.now()}-${randomBytes(6).toString("hex")}-${safeName}`;
  const target = path.join(uploads, storedName);
  if (!inside(sessionRoot, target)) throw Object.assign(new Error("Upload path escapes session workspace"), { code: "PATH_ESCAPE", status: 400 });
  const handle = await open(target, "wx", 0o600);
  try {
    await handle.writeFile(data);
  } finally {
    await handle.close();
  }
  const canonicalTarget = await realpath(target);
  const entry = {
    schemaVersion: 1,
    id: randomUUID(),
    sessionId,
    name: safeName,
    source: "public-upload",
    mediaType: String(mediaType || "application/octet-stream").slice(0, 200),
    bytes: data.byteLength,
    createdAt: new Date().toISOString(),
    realPath: canonicalTarget,
    sha256: createHash("sha256").update(data).digest("hex")
  };
  await atomicRecord(root, entry);
  return publicView(entry);
}

export async function resolveSessionFile(root, sessionId, fileId) {
  const entry = await loadRecord(root, assertSessionId(sessionId), assertFileId(fileId));
  const resolved = await realpath(entry.realPath);
  if (resolved !== entry.realPath) throw Object.assign(new Error("Session file target changed after registration"), { code: "SESSION_FILE_TARGET_CHANGED", status: 409 });
  const info = await stat(resolved);
  if (!info.isFile()) throw Object.assign(new Error("Session file is no longer a regular file"), { code: "SESSION_FILE_NOT_FILE", status: 409 });
  if (entry.source === "public-upload") {
    const canonicalSessionRoot = await realpath(sessionDirectory(root, sessionId));
    if (!inside(canonicalSessionRoot, resolved)) {
      throw Object.assign(new Error("Uploaded file escaped its session workspace"), { code: "PATH_ESCAPE", status: 409 });
    }
  }
  return { ...entry, bytes: info.size, realPath: resolved };
}

export function toPublicFile(entry) {
  return publicView(entry);
}
