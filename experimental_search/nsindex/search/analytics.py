"""
Search Analytics
================
Runtime statistics for search operations.
Designed for future dashboard integration.
"""

import time
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class SearchMetrics:
    """Metrics for a single search operation."""
    query: str = ""
    total_time_ms: float = 0.0
    ranking_time_ms: float = 0.0
    snippet_time_ms: float = 0.0
    results_count: int = 0
    cache_hit: bool = False
    documents_searched: int = 0


class SearchAnalytics:
    """
    Collects and exposes search runtime statistics.
    """

    def __init__(self):
        self._searches: List[SearchMetrics] = []
        self._total_searches = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_search_time = 0.0
        self._total_ranking_time = 0.0
        self._total_snippet_time = 0.0

    def record_search(self, metrics: SearchMetrics):
        """Record metrics for a search operation."""
        self._searches.append(metrics)
        self._total_searches += 1
        self._total_search_time += metrics.total_time_ms
        self._total_ranking_time += metrics.ranking_time_ms
        self._total_snippet_time += metrics.snippet_time_ms

        if metrics.cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def get_stats(self) -> Dict:
        """Get aggregated statistics."""
        avg_search = self._total_search_time / self._total_searches if self._total_searches > 0 else 0
        avg_ranking = self._total_ranking_time / self._total_searches if self._total_searches > 0 else 0
        avg_snippet = self._total_snippet_time / self._total_searches if self._total_searches > 0 else 0
        cache_rate = self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0

        return {
            "total_searches": self._total_searches,
            "avg_search_time_ms": round(avg_search, 2),
            "avg_ranking_time_ms": round(avg_ranking, 2),
            "avg_snippet_time_ms": round(avg_snippet, 2),
            "cache_hit_rate": round(cache_rate, 4),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_search_time_ms": round(self._total_search_time, 2),
        }

    def format_stats(self) -> str:
        """Format statistics as readable string."""
        stats = self.get_stats()
        lines = [
            "=== Search Analytics ===",
            f"Total Searches:       {stats['total_searches']}",
            f"Avg Search Time:      {stats['avg_search_time_ms']:.1f} ms",
            f"Avg Ranking Time:     {stats['avg_ranking_time_ms']:.1f} ms",
            f"Avg Snippet Time:     {stats['avg_snippet_time_ms']:.1f} ms",
            f"Cache Hit Rate:       {stats['cache_hit_rate']:.1%}",
            f"Cache Hits:           {stats['cache_hits']}",
            f"Cache Misses:         {stats['cache_misses']}",
            "======================",
        ]
        return "\n".join(lines)

    def reset(self):
        """Reset all statistics."""
        self._searches.clear()
        self._total_searches = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_search_time = 0.0
        self._total_ranking_time = 0.0
        self._total_snippet_time = 0.0
