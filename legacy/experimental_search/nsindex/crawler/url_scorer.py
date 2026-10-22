"""
URL Quality Scorer
==================
Assigns crawl priority scores to URLs.
"""

from typing import List, Tuple
from urllib.parse import urlparse, parse_qs


class URLScorer:
    """
    Scores URLs for crawl priority.
    Higher score = crawl first.
    """

    # Positive signals (boost score)
    POSITIVE_PATHS = [
        "/docs/", "/documentation/", "/reference/", "/api/",
        "/tutorial/", "/guide/", "/learn/", "/wiki/",
        "/blog/", "/news/", "/articles/",
        "/about/", "/overview/", "/introduction/",
    ]

    # Negative signals (reduce score)
    NEGATIVE_PATHS = [
        "/login", "/signup", "/sign-up", "/register",
        "/cart", "/checkout", "/purchase",
        "/privacy", "/terms", "/legal", "/cookie",
        "/search", "/tag/", "/tags/",
        "/archive", "/page=", "/offset=",
        "/wp-admin", "/wp-login",
        "/admin", "/dashboard",
    ]

    def __init__(self):
        self._domain_weights: dict = {}

    def score(self, url: str) -> int:
        """
        Calculate priority score for a URL.
        Range: -100 to +100
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parse_qs(parsed.query)

        score = 0

        # Path analysis
        for positive in self.POSITIVE_PATHS:
            if positive in path:
                score += 10
                break

        for negative in self.NEGATIVE_PATHS:
            if negative in path:
                score -= 15
                break

        # Depth penalty (deeper = lower priority)
        depth = len([p for p in path.split("/") if p])
        score -= depth * 2

        # Query parameter penalty
        if query:
            score -= len(query) * 5

        # Shorter URL bonus
        if len(path) < 20:
            score += 5

        # Domain weight bonus
        domain_weight = self._domain_weights.get(parsed.netloc, 0.5)
        score += int(domain_weight * 10)

        return max(-100, min(100, score))

    def set_domain_weight(self, domain: str, weight: float):
        """Set weight for a domain (0.0 - 1.0)."""
        self._domain_weights[domain] = max(0.0, min(1.0, weight))

    def rank_urls(self, urls: List[str]) -> List[Tuple[str, int]]:
        """Rank URLs by priority score."""
        scored = [(url, self.score(url)) for url in urls]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
