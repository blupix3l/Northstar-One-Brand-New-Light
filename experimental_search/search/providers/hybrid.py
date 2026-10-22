"""
Hybrid Search Provider
======================
Combines NSIndex (fast local) + Brave (web) for best results.
"""

import time
from typing import List
from ..provider import SearchProvider
from ..models import SearchResult


class HybridProvider(SearchProvider):
    """Merges local NSIndex results with Brave web results."""

    name = "hybrid"

    def __init__(self, nsindex_provider, brave_provider):
        self._nsindex = nsindex_provider
        self._brave = brave_provider

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        start = time.perf_counter()

        # Step 1: Query NSIndex (fast, local)
        ns_results = self._nsindex.search(query, limit=limit)

        # Step 2: Query Brave (web)
        brave_results = self._brave.search(query, limit=limit)

        # Step 3: Merge + deduplicate by URL
        seen_urls = set()
        merged = []

        # NSIndex results first (local, trusted)
        for r in ns_results:
            key = r.url.rstrip("/").lower()
            if key not in seen_urls:
                seen_urls.add(key)
                r.score += 5.0  # Boost local results
                merged.append(r)

        # Brave results second (web, fill gaps)
        for r in brave_results:
            key = r.url.rstrip("/").lower()
            if key not in seen_urls:
                seen_urls.add(key)
                merged.append(r)

        # Step 4: Re-rank by score
        merged.sort(key=lambda r: r.score, reverse=True)

        merge_ms = (time.perf_counter() - start) * 1000
        print(f'[SEARCH]\nProvider: Hybrid\nQuery: "{query}"\n'
              f'NSIndex: {len(ns_results)} | Brave: {len(brave_results)}\n'
              f'Merge Time: {merge_ms:.1f} ms\n'
              f'Results: {len(merged[:limit])}\n')

        return merged[:limit]

    def close(self):
        self._nsindex.close()
        self._brave.close()
