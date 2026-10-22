"""
Search Result Model
===================
Standardized dataclass for all search providers.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    """Standardized search result returned by all providers."""

    title: str
    url: str
    display_url: str = ""
    snippet: str = ""
    favicon: Optional[str] = None
    source: str = ""
    score: float = 0.0

    def __post_init__(self):
        if not self.display_url:
            self.display_url = self.url

    def __eq__(self, other):
        if not isinstance(other, SearchResult):
            return False
        return self.url.rstrip("/") == other.url.rstrip("/")

    def __hash__(self):
        return hash(self.url.rstrip("/"))
