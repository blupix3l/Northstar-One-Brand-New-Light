"""NSIndex Scrapers — Content extraction from web pages."""

from .base import BaseScraper
from .registry import ScraperRegistry
from .generic import GenericScraper

__all__ = ["BaseScraper", "ScraperRegistry", "GenericScraper"]
