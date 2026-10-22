"""
Scraper Registry
================
Automatically selects the correct scraper for a URL.
Extensible — no giant if/else chains.
"""

from typing import Dict, Type, Optional
from .base import BaseScraper
from ..fetcher.response import RawResponse
from ..models.page_document import PageDocument


class ScraperRegistry:
    """
    Registry that maps domains to scrapers.
    Falls back to GenericScraper for unknown domains.
    """

    def __init__(self):
        self._scrapers: Dict[str, BaseScraper] = {}
        self._default_scraper: Optional[BaseScraper] = None
        self._fallback: Optional[BaseScraper] = None

    def register(self, domain: str, scraper: BaseScraper):
        """Register a scraper for a specific domain."""
        self._scrapers[domain] = scraper

    def set_default(self, scraper: BaseScraper):
        """Set the default scraper for all domains."""
        self._default_scraper = scraper

    def set_fallback(self, scraper: BaseScraper):
        """Set the fallback scraper (used when no specific scraper matches)."""
        self._fallback = scraper

    def get_scraper(self, url: str) -> BaseScraper:
        """Get the appropriate scraper for a URL."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()

        # Check domain-specific scrapers
        if domain in self._scrapers:
            return self._scrapers[domain]

        # Check subdomain matching (e.g., www.youtube.com -> youtube.com)
        parts = domain.split(".")
        if len(parts) >= 2:
            base_domain = ".".join(parts[-2:])
            if base_domain in self._scrapers:
                return self._scrapers[base_domain]

        # Use default or fallback
        if self._default_scraper:
            return self._default_scraper
        if self._fallback:
            return self._fallback

        raise ValueError(f"No scraper registered for {domain}")

    def extract(self, response: RawResponse) -> PageDocument:
        """Extract content using the appropriate scraper."""
        scraper = self.get_scraper(response.url)
        return scraper.extract(response)

    @property
    def registered_domains(self) -> list:
        return list(self._scrapers.keys())
