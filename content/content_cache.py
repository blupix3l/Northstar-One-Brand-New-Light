"""
Content Cache
=============
Permanent cache for PageProfiles. One URL = One profile.
No expiry — only regenerate if missing, manual refresh, or corruption.
"""

import os
import json
import time
from typing import Optional
from .page_profile import PageProfile


class ContentCache:
    """
    Disk-backed permanent cache for PageProfiles.

    Storage: ~/.northstar/content_cache/<domain>/<path>.json
    """

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".northstar", "content_cache")
        self._cache_dir = cache_dir
        self._memory_cache: dict[str, PageProfile] = {}
        os.makedirs(self._cache_dir, exist_ok=True)

    def _key_path(self, url: str) -> str:
        """Convert URL to a filesystem-safe cache path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or "unknown"
        path = parsed.path.strip("/") or "index"
        # Sanitize
        domain = "".join(c if c.isalnum() or c in ".-" else "_" for c in domain)
        path = "".join(c if c.isalnum() or c in "-_" else "_" for c in path)[:120]
        return os.path.join(self._cache_dir, domain, f"{path}.json")

    def get(self, url: str) -> Optional[PageProfile]:
        """
        Retrieve cached profile for URL.
        Returns None if not cached or corrupted.
        """
        # Memory cache first
        if url in self._memory_cache:
            return self._memory_cache[url]

        # Disk cache
        path = self._key_path(url)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = PageProfile.from_dict(data)
            self._memory_cache[url] = profile
            return profile
        except Exception:
            # Corrupted — remove
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def put(self, profile: PageProfile):
        """Store a PageProfile permanently."""
        if not profile.url:
            return

        # Update memory cache
        self._memory_cache[profile.url] = profile

        # Write to disk
        path = self._key_path(profile.url)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            data = profile.to_dict()
            data["last_updated"] = time.time()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ENRICH] Cache write failed for {profile.url}: {e}")

    def has(self, url: str) -> bool:
        """Check if URL is cached (memory or disk)."""
        if url in self._memory_cache:
            return True
        return os.path.exists(self._key_path(url))

    def invalidate(self, url: str):
        """Remove a cached profile."""
        self._memory_cache.pop(url, None)
        path = self._key_path(url)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def clear(self):
        """Clear all cached profiles."""
        self._memory_cache.clear()
        import shutil
        if os.path.exists(self._cache_dir):
            shutil.rmtree(self._cache_dir)
            os.makedirs(self._cache_dir, exist_ok=True)

    def stats(self) -> dict:
        """Return cache statistics."""
        total = 0
        for root, dirs, files in os.walk(self._cache_dir):
            total += sum(1 for f in files if f.endswith(".json"))
        return {
            "total_profiles": total,
            "memory_cached": len(self._memory_cache),
            "cache_dir": self._cache_dir,
        }
