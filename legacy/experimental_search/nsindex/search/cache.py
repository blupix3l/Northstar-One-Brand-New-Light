"""
Result Cache
============
LRU cache for search results with automatic invalidation.
"""

import time
from typing import List, Optional, Dict
from collections import OrderedDict
from .results import SearchResult


class ResultCache:
    """
    LRU cache for search results.
    Invalidates affected entries when content changes.
    """

    def __init__(self, max_size: int = 500, ttl: int = 3600):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (results, timestamp)
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: str, limit: int) -> str:
        """Generate cache key from query and limit."""
        return f"{query.strip().lower()}::{limit}"

    def get(self, query: str, limit: int = 10) -> Optional[List[SearchResult]]:
        """Get cached results. Returns None on miss."""
        key = self._make_key(query, limit)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        results, timestamp = entry
        if time.time() - timestamp > self._ttl:
            # Expired
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return results

    def put(self, query: str, results: List[SearchResult], limit: int = 10):
        """Store results in cache."""
        key = self._make_key(query, limit)
        self._cache[key] = (results, time.time())

        # Evict oldest if over limit
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate_query(self, query: str):
        """Remove all cache entries for a query."""
        keys_to_remove = [k for k in self._cache if k.startswith(query.strip().lower())]
        for k in keys_to_remove:
            del self._cache[k]

    def invalidate_all(self):
        """Clear entire cache."""
        self._cache.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> Dict:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
        }
