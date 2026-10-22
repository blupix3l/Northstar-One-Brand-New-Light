"""
Regression/integration tests for the optional search providers.

Covers (no network required):
  - ddgr missing / installed (mocked subprocess)
  - duckduckgo-search library success (mocked import)
  - subprocess timeout / failure
  - fd / rg unavailable
  - provider ordering (via _LIVE_ORDER)
  - deduplication across providers
  - SearchResult conversion

Run:  python -m unittest tests.test_optional_providers -v
"""

import os
import sys
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from experimental_search.search.models import SearchResult
    from experimental_search.search.provider import SearchProvider
    from experimental_search.search.manager import SearchManager, _LIVE_ORDER
    from experimental_search.search.providers.ddgr import DDGRProvider
    from experimental_search.search.providers.duckduckgo_lib import DuckDuckGoLibProvider
    from experimental_search.search.providers.fd import FdProvider
    from experimental_search.search.providers.ripgrep import RipGrepProvider
    _DEPS_OK = True
except Exception:  # pragma: no cover - depends on optional requests
    _DEPS_OK = False

skip_msg = "optional dependency 'requests' not installed"


def _sres(title, url, source, snippet="", score=0.0):
    return SearchResult(title=title, url=url, snippet=snippet, source=source, score=score)


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestDDGRProvider(unittest.TestCase):
    def _fake_provider(self, exe_present=True):
        with patch("shutil.which", return_value=("/usr/bin/ddgr" if exe_present else None)):
            p = DDGRProvider()
        return p

    def test_missing_executable_returns_empty(self):
        p = self._fake_provider(exe_present=False)
        self.assertFalse(p.available)
        self.assertEqual(p.search("python", limit=5), [])

    def test_installed_returns_results(self):
        p = self._fake_provider(exe_present=True)
        self.assertTrue(p.available)
        payload = '{"title": "Python", "link": "https://python.org", "snippet": "x"}\n'
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")
        with patch("subprocess.run", return_value=fake):
            out = p.search("python", limit=5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], SearchResult)
        self.assertEqual(out[0].url, "https://python.org")
        self.assertEqual(out[0].source, "ddgr")

    def test_subprocess_failure_returns_empty(self):
        p = self._fake_provider(exe_present=True)
        fake = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="err")
        with patch("subprocess.run", return_value=fake):
            self.assertEqual(p.search("q", limit=5), [])

    def test_subprocess_timeout_returns_empty(self):
        p = self._fake_provider(exe_present=True)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ddgr", timeout=1)):
            self.assertEqual(p.search("q", limit=5), [])


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestDuckDuckGoLibProvider(unittest.TestCase):
    def test_success_with_mocked_library(self):
        p = DuckDuckGoLibProvider()
        # Emulate a successful library import + DDGS context manager.
        fake_ddgs_instance = MagicMock()
        fake_ddgs_instance.text.return_value = [
            {"title": "Python", "href": "https://python.org", "body": "snip"},
        ]
        fake_cls = MagicMock()
        fake_cls.return_value.__enter__.return_value = fake_ddgs_instance
        p._DDGS = fake_cls
        p.available = True
        out = p.search("python", limit=5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], SearchResult)
        self.assertEqual(out[0].url, "https://python.org")
        self.assertEqual(out[0].source, "ddglib")

    def test_unavailable_returns_empty(self):
        p = DuckDuckGoLibProvider()
        p.available = False
        p._DDGS = None
        self.assertEqual(p.search("q", limit=5), [])


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestLocalProviders(unittest.TestCase):
    def test_fd_unavailable(self):
        with patch("shutil.which", return_value=None):
            p = FdProvider()
        self.assertFalse(p.available)
        self.assertEqual(p.search("main", limit=5), [])

    def test_rg_unavailable(self):
        with patch("shutil.which", return_value=None):
            p = RipGrepProvider()
        self.assertFalse(p.available)
        self.assertEqual(p.search("def ", limit=5), [])

    def test_fd_returns_local_file_results(self):
        with patch("shutil.which", return_value="/usr/bin/fd"):
            p = FdProvider()
        self.assertTrue(p.available)
        root = tempfile.gettempdir()
        path = os.path.join(root, "myfile.txt")
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=path + "\n", stderr="")
        with patch("subprocess.run", return_value=fake):
            out = p.search("myfile", limit=5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], SearchResult)
        self.assertEqual(out[0].source, "Local File")
        self.assertTrue(out[0].url.startswith("file://"))

    def test_rg_tags_code_vs_content(self):
        with patch("shutil.which", return_value="/usr/bin/rg"):
            p = RipGrepProvider()
        root = tempfile.gettempdir()
        py_path = os.path.join(root, "a.py")
        md_path = os.path.join(root, "b.md")
        stdout = f"{py_path}:1:def main():\n{md_path}:3:some text\n"
        fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        with patch("subprocess.run", return_value=fake):
            out = p.search("def", limit=5)
        self.assertEqual(len(out), 2)
        tags = {r.source for r in out}
        self.assertIn("Local Code", tags)
        self.assertIn("Local Content", tags)


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestProviderOrderingAndDedup(unittest.TestCase):
    def test_live_order_includes_new_providers(self):
        for key in ("nsindex", "ddglib", "ddgr", "duckduckgo", "brave", "fd", "rg"):
            self.assertIn(key, _LIVE_ORDER)

    def test_dedup_across_providers(self):
        mgr = SearchManager()

        class Fake(SearchProvider):
            def __init__(self, name, results, delay=0.0):
                self.name = name
                self._r = results
                self._d = delay
            def search(self, query, limit=10):
                import time
                if self._d:
                    time.sleep(self._d)
                return [r for r in self._r if r.url]

        mgr._nsindex = Fake("nsindex", [_sres("A", "https://x.com/a", "nsindex", score=5)])
        mgr._ddglib = Fake("ddglib", [_sres("A2", "https://x.com/a/", "ddglib", score=9)])  # dup of a
        mgr._ddgr = Fake("ddgr", [_sres("B", "https://x.com/b", "ddgr")])
        mgr._ddg = Fake("duckduckgo", [])
        mgr._brave = Fake("brave", [])
        mgr._fd = Fake("Local File", [])
        mgr._rg = Fake("Local Code", [])

        out = mgr._gather("q", limit=20)
        urls = [r.url for r in out]
        # x.com/a appears only once despite two providers.
        self.assertEqual(urls.count("https://x.com/a"), 1)
        self.assertIn("https://x.com/b", urls)
        self.assertEqual(len(out), 2)

    def test_unavailable_providers_skipped_in_gather(self):
        mgr = SearchManager()
        called = {}

        class Fake(SearchProvider):
            def __init__(self, name, results, available=True):
                self.name = name
                self._r = results
                self.available = available
            def search(self, query, limit=10):
                called[self.name] = called.get(self.name, 0) + 1
                return [r for r in self._r if r.url]

        mgr._nsindex = Fake("nsindex", [_sres("A", "https://x.com/a", "nsindex")])
        mgr._ddglib = Fake("ddglib", [], available=False)   # should be skipped
        mgr._ddgr = Fake("ddgr", [_sres("B", "https://x.com/b", "ddgr")])
        mgr._ddg = Fake("duckduckgo", [])
        mgr._brave = Fake("brave", [])
        mgr._fd = Fake("Local File", [])
        mgr._rg = Fake("Local Code", [])

        mgr._gather("q", limit=20)
        self.assertNotIn("ddglib", called)  # skipped, never called


if __name__ == "__main__":
    unittest.main()
