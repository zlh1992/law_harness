"""Small, dependency-free OKF v0.2 reader/writer for the local legal knowledge bundle.

The module is shared by the MCP facade and its tests, so validation, search,
resource rendering, graph data, and transactional mutations use the same
interpretation of Markdown/YAML rather than drifting independently.

The frontmatter reader implements the portable subset used by this repository:
maps, lists, scalars, and JSON-style inline lists/maps.  It also returns a
clear parse error for YAML features that need a full YAML implementation
instead of silently discarding compliance metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import Any, Iterable


OKF_VERSION = "0.2"
MAX_DOCUMENTS = 2_000
MAX_MARKDOWN_CHARS = 1_000_000
RESERVED_FILENAMES = {"index.md", "log.md"}
VALID_STATUSES = {"draft", "stable", "deprecated"}
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
WIKILINK = re.compile(r"(?<!\\)\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class OkfError(ValueError):
    """Raised for a request that cannot be safely served from the bundle."""


_MUTATION_LOCK = RLock()
_CONCEPT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,240}$")
_METADATA_KEY = re.compile(r"^[A-Za-z0-9_.-]+$")


def _validate_concept_id(value: Any) -> str:
    concept_id = str(value or "").strip().replace("\\", "/").strip("/")
    if not _CONCEPT_ID.fullmatch(concept_id) or concept_id.casefold().endswith(".md"):
        raise OkfError("concept_id must be a relative path-like id without .md")
    parts = concept_id.split("/")
    if any(part in {"", ".", ".."} for part in parts) or f"{parts[-1]}.md".casefold() in RESERVED_FILENAMES:
        raise OkfError("concept_id contains an unsafe or reserved path")
    return concept_id


def _json_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise OkfError("metadata must contain only JSON-compatible values")


def _render_markdown(metadata: dict[str, Any], body: str) -> str:
    if not isinstance(metadata, dict):
        raise OkfError("metadata must be an object")
    lines = ["---"]
    for key, value in metadata.items():
        if not isinstance(key, str) or not _METADATA_KEY.fullmatch(key):
            raise OkfError("metadata keys must be simple YAML names")
        lines.append(f"{key}: {_json_scalar(value)}")
    lines.extend(["---", "", body.rstrip("\n"), ""])
    rendered = "\n".join(lines)
    if len(rendered) > MAX_MARKDOWN_CHARS:
        raise OkfError(f"document exceeds {MAX_MARKDOWN_CHARS} characters")
    return rendered


def _revision(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _strip_comment(line: str) -> str:
    """Remove an unquoted YAML comment (URLs and quoted text stay intact)."""

    quote = ""
    escaped = False
    for index, character in enumerate(line):
        if quote:
            if character == "\\" and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                quote = ""
            escaped = False
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
    return line.rstrip()


def _scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise OkfError(f"invalid quoted YAML string: {exc.msg}") from exc
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise OkfError("unterminated single-quoted YAML string")
        return value[1:-1].replace("''", "'")
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise OkfError(f"inline YAML values must use JSON syntax: {exc.msg}") from exc
    if re.fullmatch(r"-?(?:0|[1-9]\d*)", value):
        return int(value)
    if re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d+", value):
        return float(value)
    return value


def _yaml_lines(raw: str) -> list[tuple[int, str, int]]:
    lines: list[tuple[int, str, int]] = []
    for number, original in enumerate(raw.splitlines(), start=1):
        if "\t" in original[: len(original) - len(original.lstrip(" \t"))]:
            raise OkfError(f"frontmatter line {number}: tabs are not supported for indentation")
        text = _strip_comment(original)
        if not text.strip():
            continue
        indent = len(text) - len(text.lstrip(" "))
        lines.append((indent, text[indent:], number))
    return lines


def _split_key_value(text: str, number: int) -> tuple[str, str]:
    match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s*(.*))?$", text)
    if not match:
        raise OkfError(f"frontmatter line {number}: expected a key followed by ':'")
    return match.group(1), match.group(2) or ""


def _parse_yaml_subset(raw: str) -> dict[str, Any]:
    """Parse the intentionally conservative YAML subset emitted by this repo."""

    lines = _yaml_lines(raw)
    if not lines:
        return {}

    def parse_block(position: int, indent: int) -> tuple[Any, int]:
        if position >= len(lines) or lines[position][0] < indent:
            return {}, position
        is_list = lines[position][0] == indent and lines[position][1].startswith("- ")
        if is_list:
            values: list[Any] = []
            while position < len(lines):
                current_indent, text, number = lines[position]
                if current_indent != indent or not text.startswith("- "):
                    break
                item = text[2:].strip()
                position += 1
                if not item:
                    if position < len(lines) and lines[position][0] > indent:
                        nested_indent = lines[position][0]
                        nested, position = parse_block(position, nested_indent)
                        values.append(nested)
                    else:
                        values.append(None)
                    continue
                if re.match(r"^[A-Za-z0-9_.-]+:", item):
                    key, value = _split_key_value(item, number)
                    record: dict[str, Any] = {}
                    if value:
                        record[key] = _scalar(value)
                    elif position < len(lines) and lines[position][0] > indent:
                        nested_indent = lines[position][0]
                        record[key], position = parse_block(position, nested_indent)
                    else:
                        record[key] = None
                    while position < len(lines) and lines[position][0] > indent:
                        child_indent, child_text, child_number = lines[position]
                        if child_text.startswith("- ") and child_indent == indent + 2:
                            break
                        if child_indent < indent + 2:
                            break
                        if child_indent != indent + 2 or child_text.startswith("- "):
                            raise OkfError(f"frontmatter line {child_number}: invalid list item indentation")
                        child_key, child_value = _split_key_value(child_text, child_number)
                        position += 1
                        if child_value:
                            record[child_key] = _scalar(child_value)
                        elif position < len(lines) and lines[position][0] > child_indent:
                            nested, position = parse_block(position, lines[position][0])
                            record[child_key] = nested
                        else:
                            record[child_key] = None
                    values.append(record)
                else:
                    values.append(_scalar(item))
                    if position < len(lines) and lines[position][0] > indent:
                        raise OkfError(f"frontmatter line {lines[position][2]}: scalar list items cannot have children")
            return values, position

        record: dict[str, Any] = {}
        while position < len(lines):
            current_indent, text, number = lines[position]
            if current_indent != indent or text.startswith("- "):
                break
            key, value = _split_key_value(text, number)
            position += 1
            if value:
                record[key] = _scalar(value)
            elif position < len(lines) and lines[position][0] > indent:
                record[key], position = parse_block(position, lines[position][0])
            else:
                record[key] = None
        return record, position

    parsed, position = parse_block(0, lines[0][0])
    if position != len(lines) or not isinstance(parsed, dict):
        raise OkfError("frontmatter must be a top-level YAML map")
    return parsed


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str, str | None]:
    if not markdown.startswith("---"):
        return {}, markdown, "missing YAML frontmatter"
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", markdown, re.DOTALL)
    if not match:
        return {}, markdown, "frontmatter opening delimiter has no closing delimiter"
    raw = match.group(1)
    try:
        return _parse_yaml_subset(raw), markdown[match.end() :], None
    except OkfError as exc:
        return {}, markdown[match.end() :], str(exc)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _metadata_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _title_from_body(body: str, fallback: str) -> str:
    match = HEADING.search(body)
    return match.group(2).strip() if match else fallback


def _relative_path(root: Path, value: Path) -> str:
    return value.relative_to(root).as_posix()


def _concept_id(relative_path: str) -> str:
    return relative_path[:-3] if relative_path.casefold().endswith(".md") else relative_path


def _safe_normalized_path(value: str) -> str | None:
    candidate = value.replace("\\", "/").strip()
    if not candidate or candidate.startswith("//") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", candidate):
        return None
    candidate = candidate.split("#", 1)[0].split("?", 1)[0]
    if candidate.startswith("/"):
        candidate = candidate[1:]
    normal = PurePosixPath(candidate)
    if any(part == ".." for part in normal.parts):
        return None
    return normal.as_posix()


def _link_target(source_path: str, raw_target: str, known_ids: set[str]) -> str | None:
    value = raw_target.strip()
    if not value or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return None
    value = value.split("#", 1)[0].split("?", 1)[0]
    if not value:
        return None
    if value.startswith("/"):
        candidate = _safe_normalized_path(value)
    else:
        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), value))
        candidate = _safe_normalized_path(normalized)
    if not candidate:
        return None
    if candidate.endswith(".md"):
        candidate = candidate[:-3]
    return candidate if candidate in known_ids else None


def _links(markdown_body: str) -> list[str]:
    targets = [match.group(1).strip().strip("<>") for match in MARKDOWN_LINK.finditer(markdown_body)]
    targets.extend(match.group(1).strip() for match in WIKILINK.finditer(markdown_body))
    return list(dict.fromkeys(target for target in targets if target))


def _parse_instant(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _trust(metadata: dict[str, Any]) -> str:
    verified = _metadata_list(metadata.get("verified"))
    actors = [_text(item.get("by")) for item in verified]
    if any(actor.startswith("human:") for actor in actors):
        return "human-reviewed"
    if verified:
        return "machine-confirmed"
    return "unverified"


def _authority(metadata: dict[str, Any]) -> dict[str, Any]:
    law = metadata.get("law") if isinstance(metadata.get("law"), dict) else {}
    return {
        "jurisdictions": _string_list(law.get("jurisdictions")),
        "authority_level": _text(law.get("authority_level")),
        "effective_from": _text(law.get("effective_from")),
        "effective_to": _text(law.get("effective_to")),
        "topics": _string_list(law.get("topics")),
    }


class LegalOkfBundle:
    """Validated in-memory view of one OKF legal knowledge bundle."""

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.documents: dict[str, dict[str, Any]] = {}
        self.concepts: dict[str, dict[str, Any]] = {}
        self.bundle_index: dict[str, Any] | None = None
        self.bundle_log: dict[str, Any] | None = None
        self._load()

    def _load(self) -> None:
        if not self.root.is_dir():
            raise OkfError("LAW_WIKI_ROOT is not an existing directory")
        paths = sorted(path for path in self.root.rglob("*.md") if path.is_file())
        if len(paths) > MAX_DOCUMENTS:
            raise OkfError(f"bundle exceeds {MAX_DOCUMENTS} Markdown documents")
        for file_path in paths:
            current_path = file_path
            while current_path != self.root:
                if current_path.is_symlink():
                    raise OkfError(f"bundle contains a symlinked Markdown path: {_relative_path(self.root, file_path)}")
                current_path = current_path.parent
            relative_path = _relative_path(self.root, file_path)
            raw = file_path.read_text(encoding="utf-8", errors="replace")
            if len(raw) > MAX_MARKDOWN_CHARS:
                raise OkfError(f"bundle page exceeds {MAX_MARKDOWN_CHARS} characters: {relative_path}")
            metadata, body, parse_error = split_frontmatter(raw)
            document = {
                "id": _concept_id(relative_path),
                "path": relative_path,
                "raw": raw,
                "body": body,
                "metadata": metadata,
                "parse_error": parse_error,
                "reserved": file_path.name.casefold() in RESERVED_FILENAMES,
                "title": _text(metadata.get("title")) or _title_from_body(body, file_path.stem),
            }
            self.documents[relative_path] = document
            if relative_path == "index.md":
                self.bundle_index = document
            if relative_path == "log.md":
                self.bundle_log = document
            if not document["reserved"]:
                self.concepts[document["id"]] = document
        known_ids = set(self.concepts)
        known_document_ids = {_concept_id(relative_path) for relative_path in self.documents}
        for concept in self.concepts.values():
            outgoing: list[str] = []
            broken: list[str] = []
            for raw_target in _links(concept["body"]):
                target = _link_target(concept["path"], raw_target, known_document_ids)
                if target:
                    if target in known_ids:
                        outgoing.append(target)
                elif not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw_target) and not raw_target.startswith("#"):
                    broken.append(raw_target)
            concept["links"] = list(dict.fromkeys(outgoing))
            concept["broken_links"] = list(dict.fromkeys(broken))
            concept["sources"] = _metadata_list(concept["metadata"].get("sources"))
            concept["trust"] = _trust(concept["metadata"])
            concept["authority"] = _authority(concept["metadata"])
            concept["status"] = _text(concept["metadata"].get("status")) or "stable"
            concept["tags"] = _string_list(concept["metadata"].get("tags"))
            concept["type"] = _text(concept["metadata"].get("type"))
            concept["description"] = _text(concept["metadata"].get("description"))
        for concept in self.concepts.values():
            concept["backlinks"] = sorted(other["id"] for other in self.concepts.values() if concept["id"] in other["links"])

    def _document_path(self, concept_id: str) -> Path:
        concept_id = _validate_concept_id(concept_id)
        root = self.root.resolve()
        target = root.joinpath(*concept_id.split("/"))
        target = target.parent / f"{target.name}.md"
        if root not in target.parents:
            raise OkfError("concept_id escapes the OKF bundle")
        current = target
        while current != root:
            if current.is_symlink():
                raise OkfError("refusing to access a symlinked OKF path")
            current = current.parent
        return target

    def _write_atomic(self, target: Path, rendered: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_symlink():
            raise OkfError("refusing to mutate a symlinked OKF document")
        root = self.root.resolve()
        parent = target.parent.resolve()
        if parent != root and root not in parent.parents:
            raise OkfError("document parent escapes the OKF bundle")
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            directory_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _validated_mutation(self, target: Path, rendered: str, previous: str | None) -> dict[str, Any]:
        with _MUTATION_LOCK:
            self._write_atomic(target, rendered)
            try:
                refreshed = LegalOkfBundle(self.root)
                report = refreshed.validate()
                if report["summary"]["errors"]:
                    raise OkfError(f"mutation failed OKF validation: {report['summary']}")
            except Exception:
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    self._write_atomic(target, previous)
                raise
            self.documents = refreshed.documents
            self.concepts = refreshed.concepts
            self.bundle_index = refreshed.bundle_index
            self.bundle_log = refreshed.bundle_log
            return {
                "id": _concept_id(_relative_path(self.root, target)),
                "path": _relative_path(self.root, target),
                "revision": _revision(rendered),
                "validation": report["summary"],
            }

    def create_concept(self, concept_id: str, *, metadata: dict[str, Any], body: str, overwrite: bool = False) -> dict[str, Any]:
        with _MUTATION_LOCK:
            target = self._document_path(concept_id)
            if target.exists() and not overwrite:
                raise OkfError("concept already exists; use update or set overwrite=true")
            metadata = dict(metadata or {})
            if not str(metadata.get("type") or "").strip():
                raise OkfError("metadata.type is required")
            if metadata.get("status") is not None and metadata["status"] not in VALID_STATUSES:
                raise OkfError("metadata.status must be draft, stable, or deprecated")
            if not isinstance(body, str) or not body.strip():
                raise OkfError("body is required and cannot be empty")
            previous = target.read_text(encoding="utf-8") if target.exists() else None
            return self._validated_mutation(target, _render_markdown(metadata, body), previous)

    def update_concept(
        self,
        concept_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        body: str | None = None,
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        with _MUTATION_LOCK:
            target = self._document_path(concept_id)
            if not target.is_file() or target.is_symlink():
                raise OkfError("concept_id must identify an existing regular Markdown document")
            previous = target.read_text(encoding="utf-8")
            if expected_revision and not expected_revision.casefold() == _revision(previous):
                raise OkfError("revision does not match the current concept; reload before updating")
            current = LegalOkfBundle(self.root).documents.get(_relative_path(self.root, target))
            if current is None or current["parse_error"]:
                raise OkfError("cannot update a concept with invalid frontmatter")
            next_metadata = dict(current["metadata"])
            if metadata is not None:
                if not isinstance(metadata, dict):
                    raise OkfError("metadata must be an object")
                next_metadata.update(metadata)
            if not str(next_metadata.get("type") or "").strip():
                raise OkfError("metadata.type is required")
            if next_metadata.get("status") is not None and next_metadata["status"] not in VALID_STATUSES:
                raise OkfError("metadata.status must be draft, stable, or deprecated")
            next_body = current["body"] if body is None else body
            if not isinstance(next_body, str) or not next_body.strip():
                raise OkfError("body is required and cannot be empty")
            return self._validated_mutation(target, _render_markdown(next_metadata, next_body), previous)

    def delete_concept(self, concept_id: str, *, expected_revision: str | None = None, force: bool = False) -> dict[str, Any]:
        with _MUTATION_LOCK:
            target = self._document_path(concept_id)
            relative_path = _relative_path(self.root, target)
            current_bundle = LegalOkfBundle(self.root)
            current = current_bundle.documents.get(relative_path)
            if current is None or current["reserved"]:
                raise OkfError("concept_id must identify an existing non-reserved concept")
            previous = current["raw"]
            if expected_revision and expected_revision.casefold() != _revision(previous):
                raise OkfError("revision does not match the current concept; reload before deleting")
            if current.get("backlinks") and not force:
                raise OkfError("concept is referenced by other concepts; pass force=true to delete it")
            target.unlink()
            try:
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                refreshed = LegalOkfBundle(self.root)
                report = refreshed.validate()
                if report["summary"]["errors"]:
                    raise OkfError(f"deletion failed OKF validation: {report['summary']}")
            except Exception:
                self._write_atomic(target, previous)
                raise
            self.documents = refreshed.documents
            self.concepts = refreshed.concepts
            self.bundle_index = refreshed.bundle_index
            self.bundle_log = refreshed.bundle_log
        return {"id": current["id"], "path": relative_path, "deleted": True, "validation": report["summary"]}

    def status(self) -> dict[str, Any]:
        report = self.validate()
        return {
            "okf_version": _text((self.bundle_index or {}).get("metadata", {}).get("okf_version")),
            "root": self.root.name,
            "documents": len(self.documents),
            "concepts": len(self.concepts),
            "validation": report["summary"],
            "readonly": False,
            "writable": True,
            "local_only": True,
        }

    def list_concepts(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        wanted_type = _text(filters.get("type")).casefold()
        wanted_status = _text(filters.get("status")).casefold()
        wanted_trust = _text(filters.get("trust")).casefold()
        wanted_tags = {tag.casefold() for tag in _string_list(filters.get("tags"))}
        wanted_jurisdiction = _text(filters.get("jurisdiction")).casefold()
        listed = []
        for concept in self.concepts.values():
            if wanted_type and concept["type"].casefold() != wanted_type:
                continue
            if wanted_status and concept["status"].casefold() != wanted_status:
                continue
            if wanted_trust and concept["trust"].casefold() != wanted_trust:
                continue
            if wanted_tags and not wanted_tags.issubset({tag.casefold() for tag in concept["tags"]}):
                continue
            if wanted_jurisdiction and wanted_jurisdiction not in {item.casefold() for item in concept["authority"]["jurisdictions"]}:
                continue
            listed.append(self._summary(concept))
        return sorted(listed, key=lambda item: (item["title"].casefold(), item["id"]))

    def _summary(self, concept: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": concept["id"],
            "path": concept["path"],
            "revision": _revision(concept["raw"]),
            "title": concept["title"],
            "description": concept["description"],
            "type": concept["type"],
            "status": concept["status"],
            "trust": concept["trust"],
            "tags": concept["tags"],
            "authority": concept["authority"],
            "source_count": len(concept["sources"]),
            "backlink_count": len(concept["backlinks"]),
        }

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        terms: list[str] = []
        for token in re.findall(r"[a-z0-9][a-z0-9_.-]+|[\u3400-\u9fff]+", query.casefold()):
            if token not in terms:
                terms.append(token)
            if re.fullmatch(r"[\u3400-\u9fff]+", token) and len(token) > 2:
                terms.extend(pair for pair in (token[index : index + 2] for index in range(len(token) - 1)) if pair not in terms)
        return terms[:24]

    @staticmethod
    def _snippet(content: str, query: str, terms: Iterable[str]) -> tuple[str, int, int]:
        lowered = content.casefold()
        positions = [lowered.find(query.casefold())] if query else []
        positions.extend(lowered.find(term) for term in terms)
        positions = [position for position in positions if position >= 0]
        anchor = min(positions) if positions else 0
        start = max(0, anchor - 220)
        end = min(len(content), anchor + 720)
        if start:
            newline = content.find("\n", start)
            if 0 <= newline < anchor:
                start = newline + 1
        snippet = content[start:end].strip()
        line_start = content.count("\n", 0, start) + 1
        return snippet, line_start, line_start + snippet.count("\n")

    def search(self, query: str, *, limit: int = 6, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise OkfError("query is required")
        limit = max(1, min(20, int(limit)))
        terms = self._query_terms(query)
        matches: list[tuple[int, dict[str, Any]]] = []
        accepted = {item["id"] for item in self.list_concepts(filters)}
        for concept in self.concepts.values():
            if concept["id"] not in accepted:
                continue
            searchable = "\n".join((concept["id"], concept["title"], concept["description"], " ".join(concept["tags"]), concept["body"])).casefold()
            score = 50 if query.casefold() in searchable else 0
            for term in terms:
                occurrences = searchable.count(term)
                score += min(occurrences, 10)
                if term in concept["id"].casefold() or term in concept["title"].casefold():
                    score += 10
            if not score:
                continue
            snippet, line_start, line_end = self._snippet(concept["body"], query, terms)
            result = self._summary(concept)
            result.update({"score": score, "line_start": line_start, "line_end": line_end, "snippet": snippet})
            matches.append((score, result))
        matches.sort(key=lambda item: (-item[0], item[1]["title"].casefold(), item[1]["id"]))
        return {"query": query, "results": [item for _, item in matches[:limit]], "count": min(len(matches), limit), "local_only": True}

    def get(self, value: str, *, section: str = "", offset: int = 0, limit: int = 1_200) -> dict[str, Any]:
        requested = value.strip().replace("\\", "/").lstrip("/")
        if requested.endswith(".md"):
            requested = requested[:-3]
        if requested not in self.concepts:
            raise OkfError("concept_id must identify an existing non-reserved OKF concept")
        concept = self.concepts[requested]
        body = concept["body"]
        if section.strip():
            target = section.strip().casefold()
            headings = list(HEADING.finditer(body))
            chosen = next((heading for heading in headings if heading.group(2).strip().casefold() == target), None)
            if chosen is None:
                raise OkfError("section was not found in the concept")
            level = len(chosen.group(1))
            following = next((heading for heading in headings if heading.start() > chosen.start() and len(heading.group(1)) <= level), None)
            body = body[chosen.start() : following.start() if following else len(body)]
        lines = body.splitlines()
        offset = max(0, int(offset))
        limit = max(1, min(2_000, int(limit)))
        rendered_lines = lines[offset : offset + limit]
        result = self._summary(concept)
        result.update({
            "content": "\n".join(rendered_lines),
            "offset": offset,
            "returned_lines": len(rendered_lines),
            "total_lines": len(lines),
            "truncated": offset + len(rendered_lines) < len(lines),
            "links": concept["links"],
            "backlinks": concept["backlinks"],
            "sources": concept["sources"],
            "generated": concept["metadata"].get("generated"),
            "verified": concept["metadata"].get("verified", []),
            "stale_after": _text(concept["metadata"].get("stale_after")),
        })
        return result

    def graph(self) -> dict[str, Any]:
        categories = sorted({concept["id"].split("/", 1)[0] if "/" in concept["id"] else "root" for concept in self.concepts.values()})
        nodes = [{"id": "okf:root", "type": "bundle", "label": self.root.name}]
        nodes.extend({"id": f"category:{category}", "type": "category", "label": category} for category in categories)
        for concept in self.concepts.values():
            nodes.append({
                "id": f"concept:{concept['id']}", "type": "concept", "concept_id": concept["id"], "label": concept["title"],
                "path": concept["path"], "concept_type": concept["type"], "status": concept["status"], "trust": concept["trust"],
                "tags": concept["tags"], "authority": concept["authority"], "description": concept["description"],
            })
        edges = [{"id": f"contains:root:{category}", "source": "okf:root", "target": f"category:{category}", "type": "contains"} for category in categories]
        for concept in self.concepts.values():
            category = concept["id"].split("/", 1)[0] if "/" in concept["id"] else "root"
            edges.append({"id": f"contains:{concept['id']}", "source": f"category:{category}", "target": f"concept:{concept['id']}", "type": "contains"})
            for target in concept["links"]:
                edges.append({"id": f"references:{concept['id']}:{target}", "source": f"concept:{concept['id']}", "target": f"concept:{target}", "type": "references"})
            for source in concept["sources"]:
                resource = _text(source.get("resource"))
                target = _link_target(concept["path"], resource, set(self.concepts)) if resource else None
                if target:
                    edges.append({"id": f"sources:{concept['id']}:{target}", "source": f"concept:{concept['id']}", "target": f"concept:{target}", "type": "sources"})
        return {"schemaVersion": 2, "readonly": True, "nodes": nodes, "edges": edges, "stats": {"documents": len(self.documents), "concepts": len(self.concepts), "categories": len(categories), "edges": len(edges)}}

    def trace_context(self, concept_id: str) -> dict[str, Any]:
        concept = self.get(concept_id, limit=120)
        return {
            "concept": {key: concept[key] for key in ("id", "title", "type", "status", "trust", "authority", "stale_after", "generated", "verified")},
            "sources": concept["sources"],
            "links": concept["links"],
            "backlinks": concept["backlinks"],
            "citation_instruction": "Only cite a source after its underlying resource has been independently read or verified; an OKF source registration is provenance metadata, not the source body.",
            "local_only": True,
        }

    def validate(self) -> dict[str, Any]:
        issues: list[dict[str, str]] = []

        def issue(severity: str, code: str, path: str, message: str) -> None:
            issues.append({"severity": severity, "code": code, "path": path, "message": message})

        if self.bundle_index is None:
            issue("error", "missing_index", "index.md", "bundle root must contain index.md")
        else:
            metadata = self.bundle_index["metadata"]
            if self.bundle_index["parse_error"]:
                issue("error", "index_frontmatter", "index.md", self.bundle_index["parse_error"])
            elif _text(metadata.get("okf_version")) != OKF_VERSION:
                issue("error", "okf_version", "index.md", f"okf_version must be {OKF_VERSION}")
        if self.bundle_log is None:
            issue("warning", "missing_log", "log.md", "OKF bundles should keep a root log.md")
        for document in self.documents.values():
            if document["reserved"]:
                continue
            path = document["path"]
            metadata = document["metadata"]
            if document["parse_error"]:
                issue("error", "frontmatter", path, document["parse_error"])
                continue
            if not _text(metadata.get("type")):
                issue("error", "missing_type", path, "non-reserved concepts require a nonempty type")
            for key in ("title", "description"):
                if not _text(metadata.get(key)):
                    issue("warning", f"missing_{key}", path, f"{key} is recommended")
            status = _text(metadata.get("status"))
            if status and status not in VALID_STATUSES:
                issue("error", "invalid_status", path, "status must be draft, stable, or deprecated")
            generated = metadata.get("generated")
            if generated is not None and (not isinstance(generated, dict) or not _text(generated.get("by")) or not _text(generated.get("at"))):
                issue("warning", "generated_shape", path, "generated should include by and at")
            for verified in _metadata_list(metadata.get("verified")):
                if not _text(verified.get("by")) or not _text(verified.get("at")):
                    issue("warning", "verified_shape", path, "each verified item should include by and at")
            stale_after = metadata.get("stale_after")
            if stale_after is not None and _parse_instant(stale_after) is None:
                issue("warning", "stale_after", path, "stale_after should be an ISO-8601 instant")
            for source in _metadata_list(metadata.get("sources")):
                if not _text(source.get("resource")):
                    issue("error", "source_resource", path, "every sources item requires resource")
                if not _text(source.get("id")):
                    issue("warning", "source_id", path, "sources should use stable id values")
            for target in document.get("broken_links", []):
                issue("warning", "broken_link", path, f"unresolved local link: {target}")
        errors = sum(item["severity"] == "error" for item in issues)
        warnings = len(issues) - errors
        return {"issues": issues, "summary": {"errors": errors, "warnings": warnings, "valid": errors == 0}}


def clamp(value: Any, lower: int, upper: int, default: int) -> int:
    try:
        return max(lower, min(upper, int(value)))
    except (TypeError, ValueError):
        return default
