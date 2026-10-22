"""
Search Cache
============
Stores search results locally for instant retrieval on repeat queries.
"""

import os
import json
import time
from typing import List, Optional
from .models import SearchResult


class SearchCache:
    """
    JSON-based search result cache.

    Cache key = provider_name + normalized query.
    """

    MAX_ENTRIES = 2000

    def __init__(self, cache_dir: str = None):
        self._cache: dict = {}

        if cache_dir is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".northstar", "search_cache")
        self._cache_dir = cache_dir
        self._cache_file = os.path.join(cache_dir, "results.json")

        self._load()

    def _load(self):
        """Load cache from disk."""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, "r") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save(self):
        """Persist cache to disk."""
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump(self._cache, f, indent=2)
        except Exception:
            pass

    def _key(self, provider: str, query: str) -> str:
        """Generate cache key from provider + query."""
        normalized = query.strip().lower()
        return f"{provider}::{normalized}"

    def get(self, provider: str, query: str) -> Optional[List[SearchResult]]:
        """
        Retrieve cached results if available.

        Returns None on cache miss.
        """
        key = self._key(provider, query)
        entry = self._cache.get(key)

        if entry is None:
            return None

        # Deserialize results
        try:
            results = []
            for data in entry.get("results", []):
                results.append(SearchResult(**data))
            return results
        except Exception:
            return None

    def put(self, provider: str, query: str, results: List[SearchResult]):
        """Store results in cache."""
        key = self._key(provider, query)

        self._cache[key] = {
            "timestamp": time.time(),
            "query": query,
            "provider": provider,
            "count": len(results),
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "display_url": r.display_url,
                    "snippet": r.snippet,
                    "favicon": r.favicon,
                    "source": r.source,
                    "score": r.score,
                }
                for r in results
            ],
        }

        # Evict oldest entries if over limit
        if len(self._cache) > self.MAX_ENTRIES:
            sorted_keys = sorted(
                self._cache.keys(),
                key=lambda k: self._cache[k].get("timestamp", 0),
            )
            for k in sorted_keys[: len(self._cache) - self.MAX_ENTRIES]:
                del self._cache[k]

        self._save()

    def invalidate(self, provider: str = None, query: str = None):
        """Clear cache entries. If provider/query given, clear only matching."""
        if provider and query:
            key = self._key(provider, query)
            self._cache.pop(key, None)
        elif provider:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{provider}::")]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()
        self._save()

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "total_entries": len(self._cache),
            "cache_file": self._cache_file,
        }
