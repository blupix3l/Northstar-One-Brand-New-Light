"""
Sitemap Discovery (Phase 4)
===========================
Advanced sitemap discovery with nested sitemap support.
"""

import re
from typing import List
from urllib.parse import urljoin


class SitemapDiscovery:
    """
    Discovers and parses sitemaps from robots.txt and HTML.
    Supports nested sitemaps.
    """

    def __init__(self):
        self._discovered_urls: set = set()

    def discover_from_robots(self, robots_content: str, base_url: str) -> List[str]:
        """Extract sitemap URLs from robots.txt."""
        urls = []
        for line in robots_content.split("\n"):
            line = line.strip().lower()
            if line.startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if sitemap_url and sitemap_url.startswith("http"):
                    urls.append(sitemap_url)
        return urls

    def discover_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract sitemap references from HTML."""
        urls = []
        pattern = r'<link[^>]+rel=["\']sitemap["\'][^>]+href=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            full_url = urljoin(base_url, match)
            urls.append(full_url)
        return urls

    def discover_common_paths(self, domain: str) -> List[str]:
        """Try common sitemap paths."""
        common = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap-index.xml",
            "/sitemap.txt",
            "/sitemaps.xml",
        ]
        return [f"https://{domain}{path}" for path in common]

    def parse_sitemap(self, content: str) -> List[str]:
        """Parse XML sitemap and extract URLs."""
        urls = []
        pattern = r'<loc>\s*(.*?)\s*</loc>'
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            url = match.strip()
            if url.startswith("http"):
                urls.append(url)
        return urls

    def parse_sitemap_index(self, content: str) -> List[str]:
        """Parse sitemap index to get nested sitemap URLs."""
        return self.parse_sitemap(content)

    def filter_new_urls(self, urls: List[str]) -> List[str]:
        """Filter out already discovered URLs."""
        new_urls = []
        for url in urls:
            if url not in self._discovered_urls:
                self._discovered_urls.add(url)
                new_urls.append(url)
        return new_urls
