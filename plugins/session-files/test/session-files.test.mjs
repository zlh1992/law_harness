import assert from "node:assert/strict";
import { mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { extractDocument, pickLocalFile, windowLines } from "../lib/index.js";
import {
  listSessionFiles,
  registerLocalReference,
  resolveSessionFile,
  sanitizeUploadName,
  storePublicUpload,
} from "../lib/storage.js";

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "law-session-files-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

test("local references keep the original real path and remain session-scoped", async (t) => {
  const root = await fixture(t);
  const source = path.join(root, "合同.txt");
  await writeFile(source, "第一条\n第二条\n", "utf8");
  const recorded = await registerLocalReference(root, "session-local", source);
  assert.equal(recorded.source, "local-reference");
  assert.equal(recorded.name, "合同.txt");
  assert.equal((await listSessionFiles(root, "session-local")).length, 1);
  assert.equal((await listSessionFiles(root, "session-other")).length, 0);
  const resolved = await resolveSessionFile(root, "session-local", recorded.id);
  assert.equal(resolved.realPath, await realpath(source));
  await assert.rejects(() => resolveSessionFile(root, "session-other", recorded.id), /not found/i);
});

test("macOS local picker returns the selected POSIX path and treats cancel as empty", async () => {
  const signal = new AbortController().signal;
  const calls = [];
  const selected = await pickLocalFile(signal, {
    platform: "darwin",
    async run(command, args) {
      calls.push({ command, args });
      return { stdout: "/Users/example/合同.pdf\n" };
    }
  });
  assert.equal(selected, "/Users/example/合同.pdf");
  assert.equal(calls[0].command, "/usr/bin/osascript");
  assert.match(calls[0].args.join(" "), /choose file/);

  const canceled = await pickLocalFile(signal, {
    platform: "darwin",
    async run() {
      throw Object.assign(new Error("canceled"), { code: 1, stderr: "execution error: User canceled. (-128)" });
    }
  });
  assert.equal(canceled, null);
});

test("public uploads are copied below their session workspace without overwrite", async (t) => {
  const root = await fixture(t);
  const first = await storePublicUpload(root, "session-public", encodeURIComponent("融资清单.md"), "text/markdown", Buffer.from("# A\n"));
  const second = await storePublicUpload(root, "session-public", encodeURIComponent("融资清单.md"), "text/markdown", Buffer.from("# B\n"));
  assert.notEqual(first.id, second.id);
  const firstResolved = await resolveSessionFile(root, "session-public", first.id);
  const secondResolved = await resolveSessionFile(root, "session-public", second.id);
  assert.notEqual(firstResolved.realPath, secondResolved.realPath);
  assert.ok(firstResolved.realPath.startsWith(path.join(await realpath(root), "session-public", "uploads") + path.sep));
  assert.equal(await readFile(firstResolved.realPath, "utf8"), "# A\n");
  assert.equal(await readFile(secondResolved.realPath, "utf8"), "# B\n");
});

test("public upload validation rejects traversal, executable types and quotas", async (t) => {
  const root = await fixture(t);
  assert.equal(sanitizeUploadName(encodeURIComponent("../safe.pdf")), "safe.pdf");
  assert.throws(() => sanitizeUploadName("payload.sh"), /not allowed/i);
  await assert.rejects(
    () => storePublicUpload(root, "session-quota", "large.txt", "text/plain", Buffer.from("12345"), { maxBytes: 4 }),
    /exceeds/i,
  );
  await storePublicUpload(root, "session-quota", "one.txt", "text/plain", Buffer.from("123"), { sessionMaxBytes: 5 });
  await assert.rejects(
    () => storePublicUpload(root, "session-quota", "two.txt", "text/plain", Buffer.from("456"), { sessionMaxBytes: 5 }),
    /quota/i,
  );
});

test("extractor and line windows return bounded readable text", async (t) => {
  const root = await fixture(t);
  const source = path.join(root, "evidence.txt");
  await writeFile(source, "zero\none\ntwo\nthree\n", "utf8");
  const projectRoot = path.resolve(import.meta.dirname, "../../..");
  const extracted = await extractDocument(
    path.join(projectRoot, ".venv/bin/python"),
    path.join(projectRoot, "services/session_file_extract.py"),
    source,
  );
  assert.equal(extracted.extractor, "text");
  const selected = windowLines(extracted.content, 2, 2);
  assert.deepEqual(selected.lines, [{ number: 2, text: "one" }, { number: 3, text: "two" }]);
  assert.equal(selected.hasMore, true);
});
