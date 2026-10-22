"""Regression tests for the omnibox URL-vs-search heuristic (_is_url).

Protects the fix where numeric input (e.g. "123") and multi-word queries
must be treated as searches, while real hosts/IPs navigate.
"""

import unittest

try:
    from experimental_search.northstar_search import _is_url
    _DEPS_OK = True
except Exception:  # pragma: no cover - depends on optional requests/PyQt6
    _DEPS_OK = False

skip_msg = "optional dependency 'requests'/'PyQt6' not installed"


@unittest.skipIf(not _DEPS_OK, skip_msg)
class TestIsUrl(unittest.TestCase):

    # --- Must be treated as URLs (navigate) ---
    def test_explicit_scheme(self):
        self.assertTrue(_is_url("https://example.com"))
        self.assertTrue(_is_url("http://example.com/path?q=1"))

    def test_localhost(self):
        self.assertTrue(_is_url("localhost"))

    def test_ipv4_literal(self):
        self.assertTrue(_is_url("127.0.0.1"))
        self.assertTrue(_is_url("192.168.1.1"))

    def test_host_with_tld(self):
        self.assertTrue(_is_url("example.com"))
        self.assertTrue(_is_url("sub.example.co.uk"))
        self.assertTrue(_is_url("node.js"))  # dotted host-like token

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertTrue(_is_url("  example.com  "))

    # --- Must be treated as searches (do NOT navigate) ---
    def test_bare_number_is_search(self):
        # Was the critical bug: previously returned True.
        self.assertFalse(_is_url("123"))

    def test_multiword_query_is_search(self):
        self.assertFalse(_is_url("vs code"))
        self.assertFalse(_is_url("python tutorial"))

    def test_query_with_space_is_search(self):
        self.assertFalse(_is_url("how to cook pasta"))

    def test_short_dotted_token_is_search(self):
        # "a.b" has no valid 2+ char TLD segment.
        self.assertFalse(_is_url("a.b"))

    def test_empty_and_blank(self):
        self.assertFalse(_is_url(""))
        self.assertFalse(_is_url("   "))
        self.assertFalse(_is_url(" \t "))


if __name__ == "__main__":
    unittest.main()
