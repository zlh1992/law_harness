import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.okf_law_core import LegalOkfBundle
from services import law_wiki_mcp as wiki


def write_bundle(root: Path) -> None:
    (root / "sources").mkdir()
    (root / "playbooks").mkdir()
    (root / "index.md").write_text('---\nokf_version: "0.2"\n---\n\n# Test bundle\n', encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    (root / "sources" / "register.md").write_text(
        "---\ntitle: Source register\ntype: Source Register\ndescription: Registered source\nstatus: stable\ntags: [\"source\"]\nsources:\n  - id: official\n    resource: \"https://agency.example/rule\"\n---\n\n# Source register\n",
        encoding="utf-8",
    )
    (root / "playbooks" / "privacy.md").write_text(
        "---\ntitle: Privacy routing\ntype: Legal Playbook\ndescription: Privacy triage\nstatus: draft\ntags: [\"privacy\", \"EU\"]\ngenerated:\n  by: process:test\n  at: \"2026-08-22T00:00:00Z\"\nsources:\n  - id: source-register\n    resource: /sources/register.md\nlaw:\n  jurisdictions: [\"EU\"]\n  authority_level: workflow\n---\n\n# Privacy routing\n\nReview [source](/sources/register.md).\n",
        encoding="utf-8",
    )


class LegalOkfBundleTests(unittest.TestCase):
    def test_parses_searches_and_connects_internal_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            write_bundle(Path(temp))
            bundle = LegalOkfBundle(temp)
            self.assertEqual(bundle.validate()["summary"], {"errors": 0, "warnings": 0, "valid": True})
            result = bundle.search("privacy", filters={"jurisdiction": "EU"})
            self.assertEqual(result["results"][0]["id"], "playbooks/privacy")
            graph = bundle.graph()
            self.assertTrue(any(edge["type"] == "sources" for edge in graph["edges"]))
            self.assertEqual(bundle.get("playbooks/privacy")["links"], ["sources/register"])

    def test_rejects_concepts_without_a_type(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_bundle(root)
            (root / "broken.md").write_text("---\ntitle: Broken\n---\n\n# Broken\n", encoding="utf-8")
            report = LegalOkfBundle(root).validate()
            self.assertTrue(any(issue["code"] == "missing_type" and issue["severity"] == "error" for issue in report["issues"]))


class LawWikiMcpTests(unittest.TestCase):
    def test_native_and_legacy_operations_use_the_same_read_only_bundle(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(wiki, "WIKI_ROOT", Path(temp)):
            write_bundle(Path(temp))
            self.assertEqual(wiki.okf_status({})["okf_version"], "0.2")
            self.assertEqual(wiki.okf_search({"query": "privacy"})["results"][0]["id"], "playbooks/privacy")
            self.assertEqual(wiki.legacy_search({"query": "privacy"})["results"][0]["path"], "playbooks/privacy.md")
            self.assertEqual(wiki.legacy_read_page({"path": "playbooks/privacy.md"})["concept_id"], "playbooks/privacy")
            resource = wiki.read_resource("lawwiki://legal-okf/concepts/playbooks/privacy")
            self.assertIn("type: Legal Playbook", resource["contents"][0]["text"])
            self.assertTrue({"search", "read_page", "catalog", "okf_validate", "okf_trace_context"}.issubset({tool["name"] for tool in wiki.TOOLS}))


if __name__ == "__main__":
    unittest.main()
