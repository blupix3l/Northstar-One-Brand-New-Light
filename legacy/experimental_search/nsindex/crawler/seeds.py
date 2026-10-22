"""
Seed Manager
============
Manages seed URLs for crawling.
"""

import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class SeedEntry:
    """A seed URL with metadata."""
    url: str
    priority: int = 0
    domain: str = ""
    added_at: float = 0.0

    def __post_init__(self):
        if not self.domain:
            from urllib.parse import urlparse
            self.domain = urlparse(self.url).netloc


class SeedManager:
    """
    Manages seed URLs for crawling.
    Supports adding, removing, prioritizing, and persistence.
    """

    def __init__(self, storage_path: str = None):
        self._seeds: Dict[str, SeedEntry] = {}
        self._storage_path = storage_path or os.path.join(
            os.path.expanduser("~"), ".northstar", "nsindex", "seeds.json"
        )
        self._load()

    def _load(self):
        """Load seeds from disk."""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                for item in data:
                    seed = SeedEntry(**item)
                    self._seeds[seed.url] = seed
        except Exception:
            self._seeds = {}

    def _save(self):
        """Persist seeds to disk."""
        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            data = [
                {"url": s.url, "priority": s.priority, "domain": s.domain, "added_at": s.added_at}
                for s in self._seeds.values()
            ]
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add(self, url: str, priority: int = 0) -> bool:
        """Add a seed URL. Returns True if added."""
        if url in self._seeds:
            return False
        import time
        self._seeds[url] = SeedEntry(url=url, priority=priority, added_at=time.time())
        self._save()
        return True

    def add_batch(self, urls: List[str], priority: int = 0) -> int:
        """Add multiple seed URLs. Returns count added."""
        count = 0
        for url in urls:
            if self.add(url, priority):
                count += 1
        return count

    def remove(self, url: str) -> bool:
        """Remove a seed URL."""
        if url in self._seeds:
            del self._seeds[url]
            self._save()
            return True
        return False

    def set_priority(self, url: str, priority: int):
        """Update priority for a seed URL."""
        if url in self._seeds:
            self._seeds[url].priority = priority
            self._save()

    def get_seeds(self, limit: int = 100) -> List[SeedEntry]:
        """Get seeds sorted by priority (highest first)."""
        seeds = sorted(self._seeds.values(), key=lambda s: s.priority, reverse=True)
        return seeds[:limit]

    def get_by_domain(self, domain: str) -> List[SeedEntry]:
        """Get all seeds for a specific domain."""
        return [s for s in self._seeds.values() if s.domain == domain]

    def get_domains(self) -> List[str]:
        """Get all unique domains from seeds."""
        return list(set(s.domain for s in self._seeds.values()))

    def count(self) -> int:
        return len(self._seeds)

    def clear(self):
        self._seeds.clear()
        self._save()
