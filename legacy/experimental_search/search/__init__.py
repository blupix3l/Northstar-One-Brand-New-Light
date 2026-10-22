"""
NorthStar Search Module
=======================
Modular provider architecture for web search.
"""

from .models import SearchResult
from .provider import SearchProvider
from .manager import SearchManager

__all__ = ["SearchResult", "SearchProvider", "SearchManager"]
