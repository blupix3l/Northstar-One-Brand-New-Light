"""
URL Frontier (Phase 4)
======================
Enhanced frontier with priorities, depth tracking, revisit scheduling.
"""

import time
from typing import List, Set, Optional, Tuple
from collections import defaultdict
from urllib.parse import urlparse, urldefrag
from .url_scorer import URLScorer
from .revisit import RevisitPolicyManager


class FrontierEntry:
    """Enhanced frontier entry with metadata."""
    __slots__ = ('url', 'priority', 'depth', 'added_at', 'retries', 'domain')

    def __init__(self, url: str, priority: int = 0, depth: int = 0):
        self.url = url
        self.priority = priority
        self.depth = depth
        self.added_at = time.time()
        self.retries = 0
        self.domain = urlparse(url).netloc


class URLFrontier:
    """
    Enhanced URL frontier with priorities, depth tracking, and deduplication.
    """

    def __init__(self):
        self._queue: List[FrontierEntry] = []
        self._visited: Set[str] = set()
        self._in_queue: Set[str] = set()
        self._domain_counts: dict = defaultdict(int)
        self._url_scorer = URLScorer()
        self._max_depth = 5

    def add(self, url: str, priority: int = 0, depth: int = 0) -> bool:
        """Add a URL to the frontier. Returns True if added."""
        url = self._normalize(url)
        if not url or url in self._visited or url in self._in_queue:
            return False

        if depth > self._max_depth:
            return False

        # Auto-score if priority not specified
        if priority == 0:
            priority = self._url_scorer.score(url)

        entry = FrontierEntry(url=url, priority=priority, depth=depth)
        self._queue.append(entry)
        self._in_queue.add(url)
        self._domain_counts[entry.domain] += 1
        return True

    def add_batch(self, urls: List[str], priority: int = 0, depth: int = 0) -> int:
        """Add multiple URLs. Returns count added."""
        return sum(1 for url in urls if self.add(url, priority, depth))

    def next(self) -> Optional[FrontierEntry]:
        """Get the next URL to crawl, sorted by priority."""
        if not self._queue:
            return None

        # Sort by priority (highest first) periodically
        if len(self._queue) > 50:
            self._queue.sort(key=lambda e: e.priority, reverse=True)

        entry = self._queue.pop(0)
        self._in_queue.discard(entry.url)
        self._visited.add(entry.url)
        return entry

    def mark_visited(self, url: str):
        """Mark a URL as visited without adding to queue."""
        self._visited.add(self._normalize(url))

    def retry(self, entry: FrontierEntry, max_retries: int = 3) -> bool:
        """Re-queue a failed URL if retries remain."""
        if entry.retries >= max_retries:
            return False
        entry.retries += 1
        entry.priority = max(0, entry.priority - 10)
        self._queue.append(entry)
        self._in_queue.add(entry.url)
        return True

    def is_visited(self, url: str) -> bool:
        return self._normalize(url) in self._visited

    def pending_count(self) -> int:
        return len(self._queue)

    def visited_count(self) -> int:
        return len(self._visited)

    def get_domain_stats(self) -> dict:
        """Get per-domain crawl counts."""
        return dict(self._domain_counts)

    def clear(self):
        self._queue.clear()
        self._visited.clear()
        self._in_queue.clear()
        self._domain_counts.clear()

    def _normalize(self, url: str) -> str:
        url = url.strip()
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc}{path}".lower()
