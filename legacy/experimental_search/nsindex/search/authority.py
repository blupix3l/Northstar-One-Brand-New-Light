"""
Domain Authority
================
Modular ranking component for domain reputation.
"""

from typing import Dict, Optional


class DomainAuthority:
    """
    Stores and retrieves domain reputation scores.
    Authority influences ranking but is decoupled from crawler.
    """

    def __init__(self, storage=None):
        self._storage = storage
        self._cache: Dict[str, float] = {}
        self._default = 0.5

    def get(self, domain: str) -> float:
        """Get authority score for a domain (0.0 - 1.0)."""
        # Check memory cache first
        if domain in self._cache:
            return self._cache[domain]

        # Check storage
        if self._storage:
            authority = self._storage.get_authority(domain)
            self._cache[domain] = authority
            return authority

        return self._default

    def set(self, domain: str, authority: float):
        """Set authority score for a domain."""
        authority = max(0.0, min(1.0, authority))
        self._cache[domain] = authority
        if self._storage:
            self._storage.set_authority(domain, authority)

    def boost_for_query(self, domain: str, query_domains: list = None) -> float:
        """
        Calculate authority boost for ranking.
        Returns multiplier (1.0 = no boost).
        """
        authority = self.get(domain)
        # Base boost from authority (0.5 = neutral, 1.0 = maximum)
        boost = 0.8 + (authority * 0.4)

        # Extra boost if domain matches query intent
        if query_domains and domain in query_domains:
            boost *= 1.2

        return boost

    def load_defaults(self):
        """Load default authority scores for well-known domains."""
        defaults = {
            "python.org": 0.95,
            "github.com": 0.98,
            "wikipedia.org": 0.96,
            "stackoverflow.com": 0.94,
            "docs.python.org": 0.93,
            "developer.mozilla.org": 0.95,
            "youtube.com": 0.92,
            "reddit.com": 0.88,
            "medium.com": 0.85,
            "news.ycombinator.com": 0.90,
        }
        for domain, authority in defaults.items():
            if domain not in self._cache:
                self.set(domain, authority)
