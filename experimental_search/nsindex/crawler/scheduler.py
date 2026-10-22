"""
Crawl Scheduler
===============
Controls crawl rate and politeness.
"""

import time
from typing import Dict


class CrawlScheduler:
    """
    Manages crawl timing and politeness delays.
    """

    def __init__(self, default_delay: float = 1.0, max_concurrent: int = 5):
        self._default_delay = default_delay
        self._max_concurrent = max_concurrent
        self._domain_last_access: Dict[str, float] = {}
        self._active_requests = 0

    def wait_time(self, domain: str) -> float:
        """Calculate how long to wait before crawling a domain."""
        last = self._domain_last_access.get(domain, 0)
        elapsed = time.time() - last
        return max(0, self._default_delay - elapsed)

    def record_access(self, domain: str):
        """Record that we accessed a domain."""
        self._domain_last_access[domain] = time.time()

    def can_crawl(self) -> bool:
        """Check if we can start a new crawl request."""
        return self._active_requests < self._max_concurrent

    def start_request(self):
        self._active_requests += 1

    def end_request(self):
        self._active_requests = max(0, self._active_requests - 1)

    @property
    def active_count(self) -> int:
        return self._active_requests
