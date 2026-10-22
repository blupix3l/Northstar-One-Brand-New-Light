"""
Enrichment Manager
==================
Orchestrates background content enrichment.
Provider-agnostic — never depends on Firecrawl directly.
"""

import os
import time
import threading
from queue import Queue, Empty
from typing import Optional, Callable, List
from dataclasses import dataclass, field

from .page_profile import PageProfile
from .content_cache import ContentCache

_DEBUG: bool = os.environ.get("NS_DEBUG", "").lower() in ("1", "true", "yes")

def _log(msg):
    if _DEBUG:
        print(msg)
from .content_provider import ContentProvider


# ── Enrichment Job ────────────────────────────────────────────────────────────

@dataclass
class EnrichmentJob:
    """A single enrichment task in the queue."""
    url: str
    priority: int = 0
    retries: int = 0
    max_retries: int = 2
    enqueued_at: float = field(default_factory=time.time)


# ── Enrichment Manager ────────────────────────────────────────────────────────

class EnrichmentManager:
    """
    Background enrichment system for web pages.

    Provider-agnostic: accepts any ContentProvider implementation.
    Firecrawl, Playwright, local parsers — all interchangeable.

    Usage:
        from content import EnrichmentManager
        from content.providers import FirecrawlContentProvider

        mgr = EnrichmentManager()
        mgr.add_provider(FirecrawlContentProvider())
        mgr.start()

        profile = mgr.get_profile("https://example.com")
        mgr.enqueue("https://example.com")
        mgr.on_profile_ready = lambda url: print(f"Ready: {url}")

        mgr.stop()
    """

    def __init__(self, worker_count: int = 2, cache_dir: str = None):
        self._cache = ContentCache(cache_dir)
        self._queue: Queue = Queue()
        self._workers: List[threading.Thread] = []
        self._worker_count = worker_count
        self._running = False
        self._lock = threading.Lock()

        # Provider chain — first available provider wins
        self._providers: List[ContentProvider] = []

        # Callbacks
        self.on_profile_ready: Optional[Callable[[str], None]] = None
        self.on_profile_updated: Optional[Callable[[str], None]] = None

    # ── Provider Management ───────────────────────────────────────────────

    def add_provider(self, provider: ContentProvider):
        """
        Register a content provider.
        Providers are tried in registration order.
        """
        self._providers.append(provider)

    def set_providers(self, providers: List[ContentProvider]):
        """Replace all providers at once."""
        self._providers = list(providers)

    def _get_provider(self) -> Optional[ContentProvider]:
        """Return the first available provider."""
        for p in self._providers:
            if p.is_available():
                return p
        return None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        """Start background worker threads."""
        if self._running:
            return
        self._running = True
        for i in range(self._worker_count):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"enrich-{i}")
            t.start()
            self._workers.append(t)
        _log(f"[ENRICH] Started {self._worker_count} workers")

    def stop(self):
        """Stop all workers gracefully."""
        self._running = False
        for _ in self._workers:
            self._queue.put(None)
        for t in self._workers:
            t.join(timeout=5)
        self._workers.clear()
        _log("[ENRICH] Stopped")

    # ── Query API ─────────────────────────────────────────────────────────

    def get_profile(self, url: str) -> Optional[PageProfile]:
        """Get cached profile. Returns None if not enriched yet."""
        return self._cache.get(url)

    def is_enriched(self, url: str) -> bool:
        """Check if URL has been enriched."""
        return self._cache.has(url)

    # ── Enqueue API ───────────────────────────────────────────────────────

    def enqueue(self, url: str, priority: int = 0, force: bool = False):
        """
        Queue a URL for enrichment.

        Args:
            url: Page URL to enrich.
            priority: Higher = processed first.
            force: Re-enrich even if cached.
        """
        if not url or not url.startswith("http"):
            return

        if not force and self._cache.has(url):
            return

        # Deduplicate
        with self._lock:
            for job in self._queue.queue:
                if job and job.url == url:
                    return

        job = EnrichmentJob(url=url, priority=priority)
        self._queue.put(job)
        _log(f"[ENRICH]\nQueueing:\n{url}\n")

    def enqueue_batch(self, urls: List[str], priority: int = 0):
        """Queue multiple URLs for enrichment."""
        for url in urls:
            self.enqueue(url, priority=priority)

    def refresh(self, url: str):
        """Force re-enrichment of a URL."""
        self._cache.invalidate(url)
        self.enqueue(url, force=True)

    # ── Worker Loop ───────────────────────────────────────────────────────

    def _worker_loop(self):
        while self._running:
            try:
                job = self._queue.get(timeout=1)
            except Empty:
                continue
            if job is None:
                break
            self._process_job(job)

    def _process_job(self, job: EnrichmentJob):
        start = time.perf_counter()

        try:
            provider = self._get_provider()
            if not provider:
                _log("[ENRICH] No available providers")
                return

            _log(f"[ENRICH]\nFetching profile via {provider.name}...\nURL: {job.url}\n")

            profile = PageProfile(url=job.url)
            profile = provider.enrich(profile)

            if profile.markdown_content:
                word_count = len(profile.markdown_content.split())
                _log(f"[ENRICH] Markdown extracted: {word_count} words")

            if profile.page_images:
                _log(f"[ENRICH] Images: {len(profile.page_images)}")

            if profile.hero_image:
                _log(f"[ENRICH] Hero image found")

            self._cache.put(profile)

            elapsed = (time.perf_counter() - start) * 1000
            _log(f"[ENRICH]\nProfile cached\nCompleted in {elapsed:.0f} ms\nURL: {job.url}\n")

            # Notify
            if self.on_profile_ready:
                try:
                    self.on_profile_ready(job.url)
                except Exception:
                    pass

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            _log(f"[ENRICH] Failed after {elapsed:.0f} ms: {e}")

            if job.retries < job.max_retries:
                job.retries += 1
                self._queue.put(job)

    def stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "running": self._running,
            "providers": [p.name for p in self._providers],
            "active_provider": self._get_provider().name if self._get_provider() else None,
            "cache": self._cache.stats(),
        }
