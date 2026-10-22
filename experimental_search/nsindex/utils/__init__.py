"""NSIndex Utils — Shared utilities."""

import re


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent comparison."""
    url = url.strip().lower()
    # Remove fragment
    if "#" in url:
        url = url.split("#")[0]
    # Remove trailing slash
    if url.endswith("/"):
        url = url[:-1]
    return url


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    return urlparse(url).netloc


def clean_html(html: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", html)
