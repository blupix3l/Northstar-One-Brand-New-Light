"""
Base Fetcher Interface
======================
Abstract interface for future parallel fetcher implementations.
"""

from abc import ABC, abstractmethod
from typing import List
from .response import RawResponse


class BaseFetcher(ABC):
    """
    Abstract interface for fetchers.
    Future implementations: async, threaded, connection-pooled.
    """

    @abstractmethod
    def fetch(self, url: str) -> RawResponse:
        """Fetch a single URL."""
        pass

    @abstractmethod
    def fetch_batch(self, urls: List[str]) -> List[RawResponse]:
        """Fetch multiple URLs."""
        pass

    @property
    @abstractmethod
    def stats(self) -> dict:
        """Fetch statistics."""
        pass
