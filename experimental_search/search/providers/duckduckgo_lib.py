"""
DuckDuckGo (duckduckgo-search library) Provider
================================================
Preferred DuckDuckGo provider. Uses the official `duckduckgo-search`
Python library (DDGS) instead of HTML scraping.

Auto-detected: available only when the library is importable. Never raises
at construction; falls back to an empty result set if the lib is missing.
"""

import time
from typing import List, Optional

from ..provider import SearchProvider
from ..models import SearchResult


class DuckDuckGoLibProvider(SearchProvider):
    """Search provider backed by the `duckduckgo-search` library."""

    name = "ddglib"

    def __init__(self, timeout: int = 4, max_results: int = 20):
        self.timeout = timeout
        self.max_results = max_results
        self._DDGS = None
        self.available = False
        try:
            from duckduckgo_search import DDGS
            self._DDGS = DDGS
            self.available = True
        except Exception:
            self.available = False

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.available or self._DDGS is None:
            return []
        start = time.perf_counter()
        results: List[SearchResult] = []
        try:
            with self._DDGS(timeout=self.timeout) as ddgs:
                for item in ddgs.text(query, max_results=min(limit, self.max_results)):
                    url = (item.get("href") or "").strip()
                    if not url:
                        continue
                    results.append(SearchResult(
                        title=item.get("title", "") or url,
                        url=url,
                        snippet=item.get("body", "") or "",
                        source=self.name,
                    ))
                    if len(results) >= limit:
                        break
        except Exception:
            results = []
        ms = (time.perf_counter() - start) * 1000
        print(f"[SEARCH] {self.name.ljust(12)} {ms:>7.0f} ms  results={len(results)}")
        return results[:limit]

    def close(self):
        self._DDGS = None
