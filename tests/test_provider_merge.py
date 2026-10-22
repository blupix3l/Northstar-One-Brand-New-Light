"""Regression tests for provider deduplication + concurrent merge.

These exercises SearchManager._gather / search() with lightweight fake
providers (no network). They protect the fix where results from multiple
providers are merged without duplicating URLs and local results rank first.

Skipped automatically if the optional `requests` dependency is not installed
(the real providers import it at module load).
"""

import os
import sys
import tempfile
import threading
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from experimental_search.search.models import SearchResult
    from experimental_search.search.provider import SearchProvider
    from experimental_search.search.manager import SearchManager
    _DEPS_OK = True

    class FakeProvider(SearchProvider):
        """Returns a fixed result list; records call count + optional latency."""

        def __init__(self, name, results, delay=0.0):
            self.name = name
            self._results = results
            self._delay = delay
            self.calls = 0
            self._lock = threading.Lock()

        def search(self, query, limit=10):
            with self._lock:
                self.calls += 1
            if self._delay:
                time.sleep(self._delay)
            return [r for r in self._results if r.url][:limit]

    def _res(title, url, source, score=0.0):
        return SearchResult(title=title, url=url, source=source, score=score)

except Exception:  # pragma: no cover - depends on optional requests
    _DEPS_OK = False

skip_msg = "optional dependency 'requests' not installed"


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestProviderDedupAndMerge(unittest.TestCase):
    def setUp(self):
        self.mgr = SearchManager()
        # Replace real providers with deterministic fakes.
        self.ns = FakeProvider("nsindex", [
            _res("Local A", "https://example.com/a", "nsindex", score=5.0),
            _res("Local B", "https://example.com/b", "nsindex", score=3.0),
        ])
        self.ddg = FakeProvider("duckduckgo", [
            # Overlaps with local 'a' (different trailing slash) -> must dedupe.
            _res("Web A", "https://example.com/a/", "duckduckgo", score=9.0),
            _res("Web C", "https://example.com/c", "duckduckgo", score=7.0),
        ])
        self.mgr._nsindex = self.ns
        self.mgr._ddg = self.ddg
        self.mgr._brave = None  # ensure brave is skipped (no key)

    def test_duplicates_are_removed(self):
        out = self.mgr.search("anything", limit=20)
        urls = [r.url for r in out]
        # example.com/a (from both nsindex + ddg, differing only by "/") -> one.
        self.assertEqual(urls.count("https://example.com/a"), 0)
        self.assertIn("https://example.com/a", urls)
        self.assertIn("https://example.com/b", urls)
        self.assertIn("https://example.com/c", urls)
        # total unique = 3 (a, b, c)
        self.assertEqual(len(out), 3)

    def test_local_results_rank_first(self):
        out = self.mgr.search("anything", limit=20)
        # nsindex result should appear before the higher-scored ddg result.
        self.assertEqual(out[0].source, "nsindex")

    def test_limit_is_respected(self):
        out = self.mgr.search("anything", limit=2)
        self.assertEqual(len(out), 2)

    def test_concurrent_execution_within_timeout(self):
        # A slow provider (2.5s) must not blow past the ~4s per-provider bound,
        # and the merged call must still complete quickly.
        slow = FakeProvider("duckduckgo", [_res("Slow", "https://slow.test/x", "duckduckgo")], delay=2.5)
        self.mgr._ddg = slow
        start = time.time()
        out = self.mgr.search("q", limit=10)
        elapsed = time.time() - start
        self.assertIn("https://slow.test/x", [r.url for r in out])
        self.assertLess(elapsed, 6.0)  # bounded, not additive across providers

    def test_results_are_cached(self):
        self.mgr.search("cacheme", limit=10)
        self.ns.calls = 0
        self.ddg.calls = 0
        again = self.mgr.search("cacheme", limit=10)
        self.assertGreater(len(again), 0)
        self.assertEqual(self.ns.calls, 0)
        self.assertEqual(self.ddg.calls, 0)

    def test_failing_provider_is_isolated(self):
        # A provider that raises must not abort the whole merge.
        class BoomProvider(FakeProvider):
            def search(self, query, limit=10):
                raise RuntimeError("provider down")

        self.mgr._ddg = BoomProvider("duckduckgo", [])
        out = self.mgr.search("q", limit=10)
        # Local results must still be returned despite the web failure.
        urls = [r.url for r in out]
        self.assertIn("https://example.com/a", urls)
        self.assertIn("https://example.com/b", urls)


if __name__ == "__main__":
    unittest.main()
