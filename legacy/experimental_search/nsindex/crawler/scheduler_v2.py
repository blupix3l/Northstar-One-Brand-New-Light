"""
Crawl Scheduler (Phase 4)
=========================
Decides which URL to crawl next.
Considers priority, revisit schedule, crawl delay, and retries.
"""

import time
from typing import Optional, List
from .url_scorer import URLScorer
from .revisit import RevisitPolicyManager


class CrawlScheduler:
    """
    Intelligent URL scheduler for crawling.
    """

    def __init__(self):
        self.url_scorer = URLScorer()
        self.revisit_manager = RevisitPolicyManager()
        self._domain_last_access = {}
        self._default_delay = 1.0
        self._max_concurrent = 5
        self._active_requests = 0

    def should_crawl(self, url: str) -> bool:
        """Check if we should crawl this URL now."""
        if not self.can_start():
            return False

        # Check crawl delay
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        delay = self._get_delay(domain)
        last = self._domain_last_access.get(domain, 0)
        if time.time() - last < delay:
            return False

        # Check revisit schedule
        if not self.revisit_manager.is_due(url):
            return False

        return True

    def can_start(self) -> bool:
        """Check if we can start a new crawl request."""
        return self._active_requests < self._max_concurrent

    def start_request(self, url: str):
        """Record that a request started."""
        self._active_requests += 1
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        self._domain_last_access[domain] = time.time()

    def end_request(self):
        """Record that a request completed."""
        self._active_requests = max(0, self._active_requests - 1)

    def _get_delay(self, domain: str) -> float:
        """Get crawl delay for a domain."""
        return self._default_delay

    def record_visit(self, url: str):
        """Record a visit for revisit scheduling."""
        self.revisit_manager.record_visit(url)

    @property
    def active_count(self) -> int:
        return self._active_requests
