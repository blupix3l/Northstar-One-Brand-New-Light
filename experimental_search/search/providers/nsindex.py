"""
NSIndex Search Provider
=======================
Local/fast path using NorthStar's internal index.
"""

import time
from typing import List
from ..provider import SearchProvider
from ..models import SearchResult


class NSIndexProvider(SearchProvider):
    """Local search provider using NorthStar's internal index."""

    name = "nsindex"

    def __init__(self):
        self._index: List[dict] = []

    def load_index(self, entries: List[dict]):
        """Load index entries. Each entry: {title, url, description}."""
        self._index = entries

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        start = time.perf_counter()
        query_lower = query.lower()
        results = []

        for entry in self._index:
            title = entry.get("title", "")
            url = entry.get("url", "")
            desc = entry.get("description", "")

            # Simple relevance: check if query words appear in title or description
            words = query_lower.split()
            score = 0.0
            for w in words:
                if w in title.lower():
                    score += 2.0
                if w in desc.lower():
                    score += 1.0

            if score > 0:
                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=desc,
                    source=self.name,
                    score=score,
                ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        search_ms = (time.perf_counter() - start) * 1000
        print(f'[SEARCH]\nProvider: NSIndex\nQuery: "{query}"\n'
              f'Search Time: {search_ms:.1f} ms\nResults: {len(results[:limit])}\n')

        return results[:limit]
