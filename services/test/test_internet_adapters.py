import unittest

from services import free_search_mcp
from services.mcp_utils import validate_public_http_url


class FreeSearchFacadeTests(unittest.TestCase):
    def test_only_follow_up_reading_tools_are_advertised(self):
        names = {tool["name"] for tool in free_search_mcp.TOOLS}
        self.assertEqual(
            names,
            {"fetch", "fetch_batch", "read_doc", "cache_search", "compare", "extract_structured", "engines"},
        )
        self.assertFalse({"search", "research", "download"} & names)

    def test_local_and_credential_bearing_urls_are_rejected(self):
        for value in ("http://127.0.0.1", "https://localhost/x", "https://user:pass@example.com"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_public_http_url(value)


if __name__ == "__main__":
    unittest.main()
