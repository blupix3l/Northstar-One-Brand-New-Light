"""
Robots.txt Checker (Phase 4)
============================
Full robots.txt support with allow/disallow/crawl-delay/sitemap.
"""

import time
from typing import Dict, List, Optional
from urllib.parse import urlparse


class RobotsChecker:
    """
    Full robots.txt compliance.
    Supports allow, disallow, crawl-delay, and sitemap directives.
    """

    def __init__(self, user_agent: str = "NorthStarBot/1.0"):
        self._user_agent = user_agent
        self._cache: Dict[str, Dict] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = 3600  # 1 hour

    def can_fetch(self, url: str) -> bool:
        """Check if we're allowed to crawl this URL."""
        parsed = urlparse(url)
        domain = parsed.netloc

        rules = self._cache.get(domain)
        if rules is None:
            return True  # No rules cached = allow

        path = parsed.path or "/"
        disallowed = rules.get("disallow", [])
        allowed = rules.get("allow", [])

        # Check allow rules first (more specific)
        for pattern in allowed:
            if path.startswith(pattern):
                return True

        # Check disallow rules
        for pattern in disallowed:
            if path.startswith(pattern):
                return False

        return True

    def get_crawl_delay(self, domain: str) -> float:
        """Get crawl delay for a domain."""
        rules = self._cache.get(domain)
        if rules:
            return rules.get("crawl_delay", 1.0)
        return 1.0

    def get_sitemaps(self, domain: str) -> List[str]:
        """Get sitemap URLs from robots.txt."""
        rules = self._cache.get(domain)
        if rules:
            return rules.get("sitemaps", [])
        return []

    def update_rules(self, domain: str, robots_content: str):
        """Parse and cache robots.txt content."""
        rules = {"allow": [], "disallow": [], "crawl_delay": 1.0, "sitemaps": []}

        current_agent = None
        for line in robots_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if key == "user-agent":
                    current_agent = value
                elif key == "allow" and (current_agent == "*" or current_agent == self._user_agent):
                    if value:
                        rules["allow"].append(value)
                elif key == "disallow" and (current_agent == "*" or current_agent == self._user_agent):
                    if value:
                        rules["disallow"].append(value)
                elif key == "crawl-delay":
                    try:
                        rules["crawl_delay"] = float(value)
                    except ValueError:
                        pass
                elif key == "sitemap":
                    if value:
                        rules["sitemaps"].append(value)

        self._cache[domain] = rules
        self._cache_time[domain] = time.time()

    def is_stale(self, domain: str) -> bool:
        """Check if cached rules are stale."""
        if domain not in self._cache_time:
            return True
        return time.time() - self._cache_time[domain] > self._cache_ttl
