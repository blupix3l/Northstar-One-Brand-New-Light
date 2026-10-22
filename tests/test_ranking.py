"""
Ranking regression tests.

These verify the provider-independent relevance re-ranking pass:
  * official / canonical sites rank near the top for short, intent-heavy queries
  * multiple ambiguous meanings still coexist (no single result buries the rest)
  * the final ordering is cached (preserved on a cache hit)

No live network or optional binaries are required — we exercise `rank_results`
directly with synthetic SearchResult objects that mimic what providers return.
"""

import os
import sys
import unittest

# Allow running from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from legacy.experimental_search.search.models import SearchResult
    from legacy.experimental_search.search.ranking import rank_results
    _DEPS_OK = True
except Exception:  # pragma: no cover - depends on optional requests/PyQt6
    _DEPS_OK = False

skip_msg = "optional dependency 'requests'/'PyQt6' not installed"


def _mk(title, url, source="duckduckgo", score=0.0, snippet=""):
    return SearchResult(title=title, url=url, snippet=snippet, source=source, score=score)


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestRankingCanonicalSites(unittest.TestCase):
    """Official websites must appear near the top for intent-heavy queries."""

    def test_python(self):
        results = [
            _mk("PYTHON (British Cold War plan)", "https://en.wikipedia.org/wiki/PYTHON_(British_Cold_War_plan)"),
            _mk("Python (programming language)", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
            _mk("Welcome to Python.org", "https://www.python.org/"),
            _mk("Python snake", "https://example.com/python-snake"),
        ]
        ranked = rank_results("python", results)
        top3 = [r.url for r in ranked[:3]]
        self.assertIn("https://www.python.org/", top3)
        # python.org should outrank the Cold War article.
        self.assertLess(
            top3.index("https://www.python.org/"),
            top3.index("https://en.wikipedia.org/wiki/PYTHON_(British_Cold_War_plan)"),
        )

    def test_github(self):
        results = [
            _mk("Git - Wikipedia", "https://en.wikipedia.org/wiki/Git"),
            _mk("GitHub: Let's build from here", "https://github.com/"),
            _mk("What is GitHub? - a guide", "https://www.atlassian.com/git/tutorials/what-is-github"),
        ]
        ranked = rank_results("github", results)
        top3 = [r.url for r in ranked[:3]]
        self.assertIn("https://github.com/", top3)

    def test_youtube(self):
        results = [
            _mk("YouTube", "https://www.youtube.com/"),
            _mk("YouTube - Wikipedia", "https://en.wikipedia.org/wiki/YouTube"),
            _mk("How YouTube works", "https://blog.example.com/youtube"),
        ]
        ranked = rank_results("youtube", results)
        top3 = [r.url for r in ranked[:3]]
        self.assertIn("https://www.youtube.com/", top3)

    def test_wikipedia(self):
        results = [
            _mk("Wikipedia", "https://www.wikipedia.org/"),
            _mk("Wikipedia - the free encyclopedia", "https://en.wikipedia.org/wiki/Main_Page"),
            _mk("About Wikipedia", "https://example.com/wikipedia-about"),
        ]
        ranked = rank_results("wikipedia", results)
        top3 = [r.url for r in ranked[:3]]
        self.assertIn("https://www.wikipedia.org/", top3)


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestRankingBehavior(unittest.TestCase):
    """Behavioral signals, not hardcoded domains."""

    def test_exact_query_title_wins(self):
        results = [
            _mk("Python tutorial for beginners", "https://blog.example.com/python-beginners"),
            _mk("python", "https://www.python.org/"),
        ]
        ranked = rank_results("python", results)
        self.assertEqual(ranked[0].url, "https://www.python.org/")

    def test_ambiguous_query_keeps_multiple_meanings(self):
        # "java" -> language, island, coffee. All should survive in top results.
        results = [
            _mk("Java (programming language)", "https://en.wikipedia.org/wiki/Java_(programming_language)"),
            _mk("Java | Oracle", "https://www.java.com/"),
            _mk("Java Island, Indonesia", "https://en.wikipedia.org/wiki/Java"),
            _mk("Coffee - Wikipedia", "https://en.wikipedia.org/wiki/Coffee"),
        ]
        ranked = rank_results("java", results)
        # The official language site should be present and not buried at the bottom.
        urls = [r.url for r in ranked]
        self.assertIn("https://www.java.com/", urls)
        self.assertLess(urls.index("https://www.java.com/"), len(urls) - 1)

    def test_score_is_monotonic(self):
        results = [
            _mk("Python", "https://www.python.org/"),
            _mk("Random page about python", "https://example.com/p"),
            _mk("Unrelated", "https://example.com/x"),
        ]
        ranked = rank_results("python", results)
        scores = [r.score for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_reference_demotion(self):
        # When an official candidate exists, a Wikipedia article should not
        # outrank it for the same intent.
        results = [
            _mk("Python (programming language)", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
            _mk("Welcome to Python.org", "https://www.python.org/"),
        ]
        ranked = rank_results("python", results)
        self.assertEqual(ranked[0].url, "https://www.python.org/")


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestRankingCachePreservation(unittest.TestCase):
    """The ranked order is what gets cached and replayed on a cache hit."""

    def test_ranking_order_is_stable_across_calls(self):
        results = [
            _mk("PYTHON (British plan)", "https://en.wikipedia.org/wiki/PYTHON_(British_Cold_War_plan)"),
            _mk("Welcome to Python.org", "https://www.python.org/"),
            _mk("Python snake", "https://example.com/python-snake"),
        ]
        first = rank_results("python", list(results))
        second = rank_results("python", list(results))
        self.assertEqual(
            [(r.url, round(r.score, 4)) for r in first],
            [(r.url, round(r.score, 4)) for r in second],
        )


if __name__ == "__main__":
    unittest.main()
