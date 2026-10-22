"""
Base Scraper
============
Abstract interface for all scrapers.
"""

from abc import ABC, abstractmethod
from ..models.page_document import PageDocument
from ..fetcher.response import RawResponse


class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.
    Every scraper must implement extract().
    """

    name: str = "base"

    @abstractmethod
    def extract(self, response: RawResponse) -> PageDocument:
        """
        Extract structured content from a raw HTTP response.
        
        Args:
            response: RawResponse from the fetcher.
            
        Returns:
            PageDocument with extracted content.
        """
        pass

    def can_handle(self, url: str) -> bool:
        """Check if this scraper can handle the given URL."""
        return False
