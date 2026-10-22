"""
Crawl Policies
==============
Configurable per-domain crawl policies.
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class CrawlPolicy:
    """Configuration for crawling a specific domain."""
    domain: str
    delay: float = 1.0          # Seconds between requests
    max_depth: int = 3          # Maximum crawl depth
    enabled: bool = True        # Whether to crawl this domain
    max_pages: int = 100        # Maximum pages to crawl
    respect_robots: bool = True # Whether to check robots.txt


class CrawlPolicyManager:
    """
    Manages per-domain crawl policies.
    """

    def __init__(self, storage=None):
        self._storage = storage
        self._policies: Dict[str, CrawlPolicy] = {}
        self._default_policy = CrawlPolicy(domain="*")

    def get_policy(self, domain: str) -> CrawlPolicy:
        """Get crawl policy for a domain."""
        # Check in-memory cache
        if domain in self._policies:
            return self._policies[domain]

        # Check storage
        if self._storage:
            stored = self._storage.get_crawl_policy(domain)
            if stored:
                policy = CrawlPolicy(
                    domain=domain,
                    delay=stored.get("delay", 1.0),
                    max_depth=stored.get("max_depth", 3),
                    enabled=stored.get("enabled", True),
                )
                self._policies[domain] = policy
                return policy

        return self._default_policy

    def set_policy(self, policy: CrawlPolicy):
        """Set crawl policy for a domain."""
        self._policies[policy.domain] = policy
        if self._storage:
            self._storage.set_crawl_policy(
                policy.domain, policy.delay, policy.max_depth, policy.enabled
            )

    def set_default(self, policy: CrawlPolicy):
        """Set default policy for all domains."""
        self._default_policy = policy

    def is_allowed(self, domain: str) -> bool:
        """Check if crawling is allowed for a domain."""
        return self.get_policy(domain).enabled

    def get_delay(self, domain: str) -> float:
        """Get crawl delay for a domain."""
        return self.get_policy(domain).delay

    def get_max_depth(self, domain: str) -> int:
        """Get max crawl depth for a domain."""
        return self.get_policy(domain).max_depth

    def load_defaults(self):
        """Load sensible default policies."""
        defaults = [
            CrawlPolicy("python.org", delay=2.0, max_depth=4),
            CrawlPolicy("github.com", delay=5.0, max_depth=2),
            CrawlPolicy("wikipedia.org", delay=1.0, max_depth=3),
            CrawlPolicy("stackoverflow.com", delay=2.0, max_depth=3),
            CrawlPolicy("youtube.com", delay=3.0, max_depth=2),
            CrawlPolicy("reddit.com", delay=2.0, max_depth=2),
        ]
        for policy in defaults:
            if policy.domain not in self._policies:
                self.set_policy(policy)
