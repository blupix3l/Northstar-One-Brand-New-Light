"""
Web Crawler
===========
Orchestrates URL discovery, robots.txt, sitemaps.
"""

import time
from typing import List, Optional, Callable
from .frontier import URLFrontier
from .scheduler import CrawlScheduler
from .robots import RobotsChecker
from .sitemap import SitemapDiscovery


class WebCrawler:
    """
    Discovers URLs to crawl.
    Responsible ONLY for URL discovery — not downloading.
    """

    def __init__(self, user_agent: str = "NorthStarBot/1.0"):
        self.frontier = URLFrontier()
        self.scheduler = CrawlScheduler()
        self.robots = RobotsChecker(user_agent)
        self.sitemap = SitemapDiscovery()
        self._on_url_found: Optional[Callable[[str], None]] = None

    def seed(self, urls: List[str]):
        """Seed the frontier with initial URLs."""
        self.frontier.add_batch(urls)

    def on_url_found(self, callback: Callable[[str], None]):
        """Register callback for new URLs discovered."""
        self._on_url_found = callback

    def discover_urls(self, html: str, source_url: str) -> List[str]:
        """
        Extract links from HTML and add to frontier.
        Returns list of newly discovered URLs.
        """
        import re
        from urllib.parse import urljoin

        # Extract href links
        pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html, re.IGNORECASE)

        new_urls = []
        for match in matches:
            full_url = urljoin(source_url, match)
            if full_url.startswith("http"):
                if self.frontier.add(full_url):
                    new_urls.append(full_url)
                    if self._on_url_found:
                        self._on_url_found(full_url)

        return new_urls

    def get_next_url(self) -> Optional[str]:
        """Get the next URL to process, respecting robots.txt."""
        while True:
            url = self.frontier.next()
            if url is None:
                return None

            if self.robots.can_fetch(url):
                return url
            # Skip disallowed URLs

    def robots_txt_discovered(self, domain: str, content: str):
        """Process discovered robots.txt content."""
        self.robots.update_rules(domain, content)
