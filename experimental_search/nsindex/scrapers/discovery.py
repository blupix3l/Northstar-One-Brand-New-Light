"""
Plugin Discovery
================
Automatic scraper discovery from the scrapers/ directory.
"""

import os
import importlib
import pkgutil
from typing import List, Type
from .base import BaseScraper
from .registry import ScraperRegistry


class ScraperDiscovery:
    """
    Automatically discovers and registers scrapers.
    Adding a new scraper only requires dropping a file into scrapers/.
    """

    @staticmethod
    def discover(scrapers_package: str = "nsindex.scrapers") -> List[Type[BaseScraper]]:
        """
        Discover all scraper classes in the scrapers package.
        Returns list of scraper classes.
        """
        scrapers = []
        package = importlib.import_module(scrapers_package)
        package_path = os.path.dirname(package.__file__)

        for importer, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if module_name.startswith("_") or module_name in ("base", "registry", "discovery"):
                continue

            try:
                module = importlib.import_module(f"{scrapers_package}.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, BaseScraper) and
                        attr is not BaseScraper and
                        hasattr(attr, 'name')):
                        scrapers.append(attr)
            except Exception as e:
                print(f"[DISCOVERY] Failed to load {module_name}: {e}")

        return scrapers

    @staticmethod
    def auto_register(registry: ScraperRegistry, scrapers_package: str = "nsindex.scrapers"):
        """
        Discover scrapers and register them automatically.
        No manual registry modifications needed.
        """
        scrapers = ScraperDiscovery.discover(scrapers_package)
        for scraper_cls in scrapers:
            try:
                scraper = scraper_cls()
                # Register based on scraper's domain mapping
                if hasattr(scraper, 'DOMAINS'):
                    for domain in scraper.DOMAINS:
                        registry.register(domain, scraper)
                print(f"[DISCOVERY] Registered scraper: {scraper.name}")
            except Exception as e:
                print(f"[DISCOVERY] Failed to instantiate {scraper_cls.__name__}: {e}")
