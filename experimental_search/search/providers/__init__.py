"""
Search Providers
================
Concrete implementations of the SearchProvider interface.
"""

from .brave import BraveSearchProvider
from .duckduckgo import DuckDuckGoProvider
from .duckduckgo_lib import DuckDuckGoLibProvider
from .ddgr import DDGRProvider
from .fd import FdProvider
from .ripgrep import RipGrepProvider
from .nsindex import NSIndexProvider
from .hybrid import HybridProvider

__all__ = [
    "BraveSearchProvider",
    "DuckDuckGoProvider",
    "DuckDuckGoLibProvider",
    "DDGRProvider",
    "FdProvider",
    "RipGrepProvider",
    "NSIndexProvider",
    "HybridProvider",
]
