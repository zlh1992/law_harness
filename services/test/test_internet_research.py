import json
import random
import threading
import unittest
from unittest.mock import patch

from services import internet_research_mcp as research


class RoutingTests(unittest.TestCase):
    def test_weighted_provider_distribution(self):
        rng = random.Random(20260819)
        counts = {provider: 0 for provider in research.ROUTING_POLICY}
        for _ in range(50_000):
            counts[research.choose_provider(rng)] += 1
        self.assertLess(abs(counts["free_search"] / 50_000 - 0.50), 0.015)
        self.assertLess(abs(counts["tavily"] / 50_000 - 0.30), 0.015)
        self.assertLess(abs(counts["exa"] / 50_000 - 0.10), 0.012)
        self.assertLess(abs(counts["serpapi"] / 50_000 - 0.10), 0.012)

    def test_failed_route_falls_back_to_tavily(self):
        calls = []

        def fake(provider, query, max_results, *, deep):
            calls.append((provider, deep))
            if provider == "exa":
                raise research.ProviderError("down")
            return [{"title": "ok", "url": "https://example.com", "excerpt": "ok", "provider": provider}]

        result = research.run_routed_search(
            "query", 5, selected_provider="exa", search_fn=fake
        )
        self.assertEqual(calls, [("exa", False), ("tavily", False)])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["provider_used"], "tavily")
        self.assertEqual(result["fallback_level"], 1)

    def test_tavily_primary_failure_retries_tavily(self):
        attempts = 0

        def flaky(provider, query, max_results, *, deep):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise research.ProviderError("temporary")
            return [{"title": "ok", "url": "https://example.com", "excerpt": "ok", "provider": provider}]

        result = research.run_routed_search(
            "query", 5, selected_provider="tavily", search_fn=flaky
        )
        self.assertEqual(attempts, 2)
        self.assertTrue(result["fallback_used"])

    def test_tavily_failure_uses_second_layer_free_search(self):
        calls = []

        def fake(provider, query, max_results, *, deep):
            calls.append(provider)
            if provider != "free_search":
                raise research.ProviderError("temporary")
            return [{"title": "ok", "url": "https://example.com", "excerpt": "ok", "provider": provider}]

        result = research.run_routed_search(
            "query", 5, selected_provider="serpapi", search_fn=fake
        )
        self.assertEqual(calls, ["serpapi", "tavily", "free_search"])
        self.assertEqual(result["provider_used"], "free_search")
        self.assertEqual(result["fallback_level"], 2)

    def test_free_search_primary_gets_one_bounded_retry_after_tavily(self):
        calls = []

        def fake(provider, query, max_results, *, deep):
            calls.append(provider)
            if provider == "free_search" and calls.count("free_search") == 2:
                return [{"title": "ok", "url": "https://example.com", "excerpt": "ok", "provider": provider}]
            raise research.ProviderError("temporary")

        result = research.run_routed_search(
            "query", 5, selected_provider="free_search", search_fn=fake
        )
        self.assertEqual(calls, ["free_search", "tavily", "free_search"])
        self.assertEqual(result["fallback_level"], 2)

    def test_permanent_tavily_error_skips_duplicate_tavily_attempt(self):
        calls = []

        def fake(provider, query, max_results, *, deep):
            calls.append(provider)
            if provider == "tavily":
                raise research.ProviderError("tavily API key is not configured")
            return [{"title": "ok", "url": "https://example.com", "excerpt": "ok", "provider": provider}]

        result = research.run_routed_search(
            "query", 5, selected_provider="tavily", search_fn=fake
        )
        self.assertEqual(calls, ["tavily", "free_search"])
        self.assertEqual(result["provider_used"], "free_search")
        self.assertEqual(result["fallback_level"], 2)


class DeepResearchTests(unittest.TestCase):
    def test_deep_research_deduplicates_and_scores_sources(self):
        def route(query, max_results, *, deep):
            self.assertTrue(deep)
            return {
                "selected_provider": "exa",
                "provider_used": "exa",
                "fallback_used": False,
                "result_count": 2,
                "results": [
                    {"title": "Official", "url": "https://agency.gov/doc?utm_source=x", "excerpt": query, "provider": "exa"},
                    {"title": "Analysis", "url": f"https://example.com/{len(query)}", "excerpt": "analysis", "provider": "exa"},
                ],
            }

        with patch.object(research, "append_audit"):
            output = research.deep_research(
                {
                    "query": "test subject",
                    "subqueries": ["test subject", "test subject official", "test subject analysis"],
                    "breadth": 3,
                    "max_results_per_query": 2,
                },
                route_fn=route,
            )
        self.assertEqual(output["coverage"]["planned_queries"], 3)
        self.assertEqual(output["coverage"]["successful_queries"], 3)
        official = next(item for item in output["sources"] if "agency.gov" in item["url"])
        self.assertEqual(len(official["matched_queries"]), 3)
        self.assertTrue(official["primary_source_hint"])
        self.assertNotIn("utm_source", official["url"])

    def test_deep_research_returns_partial_packet_at_time_budget(self):
        release = threading.Event()

        def slow_route(query, max_results, *, deep):
            self.assertTrue(deep)
            release.wait(1)
            return {
                "selected_provider": "free_search",
                "provider_used": "free_search",
                "fallback_used": False,
                "result_count": 1,
                "results": [{"title": query, "url": "https://example.com", "excerpt": query, "provider": "free_search"}],
            }

        try:
            with patch.object(research, "append_audit"):
                output = research.deep_research(
                    {"query": "test subject", "subqueries": ["one", "two", "three"], "breadth": 3},
                    route_fn=slow_route,
                    time_budget_seconds=0.01,
                )
        finally:
            release.set()
        self.assertEqual(output["coverage"]["successful_queries"], 0)
        self.assertEqual(output["coverage"]["failed_queries"], 3)
        self.assertEqual({item["error"] for item in output["failures"]}, {"time_budget_exceeded"})
        self.assertLess(output["coverage"]["elapsed_ms"], 500)

    def test_status_never_contains_secret_values(self):
        encoded = json.dumps(research.status({}))
        self.assertNotIn("api_key", encoded.lower())


if __name__ == "__main__":
    unittest.main()
