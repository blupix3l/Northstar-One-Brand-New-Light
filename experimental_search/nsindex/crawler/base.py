"""
Base Crawler Interface
======================
Abstract interface for future parallel crawler implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from ..fetcher.response import RawResponse


class BaseCrawler(ABC):
    """
    Abstract interface for crawlers.
    Future implementations: threaded, async, distributed.
    """

    @abstractmethod
    def seed(self, urls: List[str]):
        """Seed the crawler with initial URLs."""
        pass

    @abstractmethod
    def get_next_url(self) -> Optional[str]:
        """Get the next URL to process."""
        pass

    @abstractmethod
    def discover_urls(self, html: str, source_url: str) -> List[str]:
        """Extract and queue new URLs from HTML."""
        pass

    @abstractmethod
    def on_url_found(self, callback: Callable[[str], None]):
        """Register callback for new URLs."""
        pass

    @property
    @abstractmethod
    def pending_count(self) -> int:
        """Number of URLs waiting to be crawled."""
        pass

    @property
    @abstractmethod
    def visited_count(self) -> int:
        """Number of URLs already crawled."""
        pass
