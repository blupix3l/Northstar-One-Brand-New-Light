"""
Content Provider Interface
==========================
Abstract base class for all content acquisition providers.

Future implementations:
  - Playwright-based extraction
  - Local HTML parsing
  - Browser-native extraction
  - Custom scrapers

Firecrawl is the first implementation.
"""

from abc import ABC, abstractmethod
from .page_profile import PageProfile


class ContentProvider(ABC):
    """
    Abstract interface for content acquisition.

    Every provider implements enrich() to populate a PageProfile
    from a URL. Providers are interchangeable — EnrichmentManager
    does not depend on any specific provider.
    """

    name: str = "base"

    @abstractmethod
    def enrich(self, profile: PageProfile) -> PageProfile:
        """
        Enrich a PageProfile with content from the URL.

        Args:
            profile: PageProfile with at least `url` set.

        Returns:
            Updated PageProfile with additional fields populated.
        """
        pass

    def is_available(self) -> bool:
        """Check if this provider is ready to use (API key set, etc.)."""
        return True
