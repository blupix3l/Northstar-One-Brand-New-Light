"""
Search Provider Base Class
==========================
Abstract base for all search providers.
"""

from abc import ABC, abstractmethod
from typing import List
from .models import SearchResult


class SearchProvider(ABC):
    """Base class all search providers must implement."""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Execute a search query and return standardized results."""
        pass

    def close(self):
        """Clean up resources. Override if needed."""
        pass
