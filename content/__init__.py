"""
NorthStar Content Module
========================
Enrichment pipeline for acquiring and caching webpage information.

Architecture:
  - ContentProvider: Abstract interface for content acquisition
  - PageProfile: Dataclass for page information
  - ContentCache: Permanent cache (one URL = one profile)
  - EnrichmentManager: Background queue with workers

Providers (swappable):
  - FirecrawlContentProvider: Firecrawl API (default)
  - Future: Playwright, local HTML parser, browser extraction, etc.
"""

from .page_profile import PageProfile
from .content_cache import ContentCache
from .content_provider import ContentProvider
from .enrichment_manager import EnrichmentManager
from .providers.firecrawl_provider import FirecrawlContentProvider

__all__ = [
    "PageProfile",
    "ContentCache",
    "ContentProvider",
    "EnrichmentManager",
    "FirecrawlContentProvider",
]
