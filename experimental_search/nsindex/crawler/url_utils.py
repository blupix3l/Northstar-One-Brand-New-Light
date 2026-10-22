"""
URL Utilities
=============
Smart link extraction, normalization, and canonical URL handling.
"""

import re
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin, urldefrag, parse_qs, urlencode, urlunparse


class URLNormalizer:
    """
    Normalizes URLs for consistent deduplication.
    Handles canonical URLs, tracking parameters, and duplicates.
    """

    # Tracking parameters to strip
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "mc_cid", "mc_eid",
        "ref", "source", "via", "share",
        "s", "t", "v", "feature",
        "_ga", "_gl", "yclid",
    }

    @staticmethod
    def normalize(url: str) -> str:
        """Normalize a URL for consistent comparison."""
        url = url.strip()
        parsed = urlparse(url)

        # Remove fragment
        path = parsed.path.rstrip("/") or "/"
        query = URLNormalizer._clean_query(parsed.query)
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()

        normalized = f"{scheme}://{netloc}{path}"
        if query:
            normalized += f"?{query}"
        return normalized

    @staticmethod
    def _clean_query(query: str) -> str:
        """Remove tracking parameters from query string."""
        if not query:
            return ""
        params = parse_qs(query, keep_blank_values=False)
        cleaned = {
            k: v for k, v in params.items()
            if k.lower() not in URLNormalizer.TRACKING_PARAMS
        }
        if not cleaned:
            return ""
        return urlencode(cleaned, doseq=True)

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is valid and crawlable."""
        if not url or not url.startswith("http"):
            return False
        parsed = urlparse(url)
        if not parsed.netloc:
            return False
        return True

    @staticmethod
    def is_crawlable(url: str) -> bool:
        """Check if URL should be crawled (not blocked schemes/paths)."""
        parsed = urlparse(url)

        # Block non-HTTP schemes
        if parsed.scheme not in ("http", "https"):
            return False

        # Block common non-page resources
        blocked_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
            ".mp3", ".mp4", ".avi", ".mov", ".wmv",
            ".zip", ".tar", ".gz", ".rar",
            ".exe", ".dmg", ".msi", ".deb", ".rpm",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".otf",
        }
        path = parsed.path.lower()
        for ext in blocked_extensions:
            if path.endswith(ext):
                return False

        return True

    @staticmethod
    def extract_links(html: str, base_url: str) -> List[str]:
        """Extract and normalize links from HTML."""
        links = []
        pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for match in matches:
            # Skip non-http links
            if not match.startswith(("http://", "https://", "/")):
                continue

            # Skip javascript: and mailto: and tel:
            if re.match(r"^(javascript:|mailto:|tel:|data:)", match):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, match)

            # Remove fragment
            full_url, _ = urldefrag(full_url)

            if URLNormalizer.is_valid_url(full_url) and URLNormalizer.is_crawlable(full_url):
                normalized = URLNormalizer.normalize(full_url)
                links.append(normalized)

        return list(set(links))  # Deduplicate

    @staticmethod
    def get_domain(url: str) -> str:
        """Extract domain from URL."""
        return urlparse(url).netloc.lower()

    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """Check if two URLs share the same domain."""
        return URLNormalizer.get_domain(url1) == URLNormalizer.get_domain(url2)
