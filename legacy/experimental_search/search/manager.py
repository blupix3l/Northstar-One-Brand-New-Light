"""
Search Manager
==============
Central coordinator for search operations.
Selects providers, executes them concurrently for speed, and returns
merged, de-duplicated results. Results are cached per merged query.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple
from .models import SearchResult
from .provider import SearchProvider
from .providers.brave import BraveSearchProvider
from .providers.duckduckgo import DuckDuckGoProvider
from .providers.duckduckgo_lib import DuckDuckGoLibProvider
from .providers.ddgr import DDGRProvider
from .providers.fd import FdProvider
from .providers.ripgrep import RipGrepProvider
from .providers.nsindex import NSIndexProvider
from .providers.hybrid import HybridProvider
from .cache import SearchCache


# ── Load .env file if present ─────────────────────────────────────────────────

def _load_env():
    """Load environment variables from .env file in parent directory."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env") if '__file__' in dir() else None,
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.getcwd()), ".env"),
    ]

    for env_path in possible_paths:
        if env_path and os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
            break

_load_env()


# Debug trace for ranking / provider decisions (NS_DEBUG=1).
_DEBUG = os.environ.get("NS_DEBUG", "").lower() in ("1", "true", "yes", "on")


# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_PROVIDER = os.environ.get("NS_SEARCH_PROVIDER", "duckduckgo")

# Per-provider attempt timeout (seconds). Local NSIndex is instant.
# Optional CLI / library providers are kept tight so a single slow backend
# can never dominate end-to-end latency.
_PROVIDER_TIMEOUT = {
    "nsindex": 0.5,
    "ddglib": 4.0,
    "ddgr": 3.0,
    "duckduckgo": 4.0,
    "brave": 4.0,
    "fd": 2.0,
    "rg": 2.0,
    "hybrid": 5.0,
}

# Hard ceiling on how long search() blocks waiting for the concurrent fan-out.
# Must comfortably exceed the slowest *fast* web provider (ddglib/ddgr @ 3-4s)
# but stay well below the old max(_PROVIDER_TIMEOUT)+1 (~7s) that let a single
# slow optional provider (e.g. ddgr) gate the entire result set.
_MERGE_BUDGET = 3.5

# Priority order for the live fan-out (local first, then fast web, then local
# filesystem search). Providers that are unavailable are skipped at runtime.
_LIVE_ORDER = ["nsindex", "ddglib", "ddgr", "duckduckgo", "brave", "fd", "rg"]


class SearchManager:
    """
    Manages search provider selection and execution with caching.

    Speed/reliability strategy:
      * Runs providers concurrently via a thread pool.
      * Each provider is bounded by a per-provider timeout so one slow
        backend can never stall the whole query.
      * Local NSIndex answers instantly and is always preferred when present.
      * Merged results are cached so repeat queries are free.

    Usage:
        manager = SearchManager()
        results = manager.search("python programming")
    """

    def __init__(self, provider_name: str = None):
        self._provider_name = provider_name or DEFAULT_PROVIDER
        self._nsindex = NSIndexProvider()
        self._brave = BraveSearchProvider()
        self._ddg = DuckDuckGoProvider()
        self._ddglib = DuckDuckGoLibProvider()
        self._ddgr = DDGRProvider()
        self._fd = FdProvider()
        self._rg = RipGrepProvider()
        self._hybrid = HybridProvider(self._nsindex, self._brave)
        self._cache = SearchCache()
        self._pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="ns-search"
        )
        self._build_provider()
        self._last_cached = False

    def _build_provider(self):
        """Instantiate the selected (single) provider for set_provider()."""
        name = self._provider_name.lower()
        if name == "hybrid":
            self._provider = self._hybrid
        elif name == "brave":
            self._provider = self._brave
        elif name == "nsindex":
            self._provider = self._nsindex
        elif name == "duckduckgo":
            self._provider = self._ddg
        else:
            self._provider = self._ddg
        if _DEBUG: print(f"[SEARCH] Active provider: {self._provider.name}")

    def set_provider(self, name: str):
        """Switch provider at runtime."""
        self._provider_name = name
        self._build_provider()

    def load_index(self, entries: List[dict]):
        """Load entries into NSIndex (used by hybrid and nsindex providers)."""
        self._nsindex.load_index(entries)

    def _gather(self, query: str, limit: int) -> List[SearchResult]:
        """Fan out across available providers concurrently and merge."""
        # Build the live provider set, skipping ones that can't answer.
        live = []
        for key in _LIVE_ORDER:
            if key == "nsindex":
                prov = self._nsindex
            elif key == "ddglib":
                prov = self._ddglib
            elif key == "ddgr":
                prov = self._ddgr
            elif key == "duckduckgo":
                prov = self._ddg
            elif key == "brave":
                prov = self._brave
            elif key == "fd":
                prov = self._fd
            elif key == "rg":
                prov = self._rg
            else:
                continue
            # Skip providers that auto-detected as unavailable (no exe / no lib).
            if getattr(prov, "available", True) is False:
                continue
            # Brave needs an API key; skip silently if absent.
            if key == "brave" and not getattr(prov, "api_key", ""):
                continue
            live.append((key, prov))

        if not live:
            return []

        merged: List[SearchResult] = []
        seen: set = set()

        futures = {
            self._pool.submit(prov.search, query, limit): key
            for key, prov in live
        }

        def _drain(pending, budget):
            """Collect completed futures into `merged` until `budget` elapses.

            `as_completed` raises `TimeoutError` when the budget elapses with
            futures still pending. We MUST catch it: the futures that completed
            *before* the timeout were already merged into `merged`, and those
            results must be returned rather than discarded. Without this guard
            a single slow optional provider (ddglib/rg) would abort the whole
            search and throw away every fast provider's results.
            """
            try:
                for fut in as_completed(list(pending), timeout=budget):
                    pending.discard(fut)
                    key = futures[fut]
                    try:
                        results = fut.result(timeout=_PROVIDER_TIMEOUT.get(key, 4.0)) or []
                    except Exception:
                        continue
                    for r in results:
                        k = r.url.rstrip("/").lower()
                        if k not in seen:
                            seen.add(k)
                            merged.append(r)
            except TimeoutError:
                pass

        # First pass: only block up to the fast budget so a slow optional
        # provider (ddgr/rg/fd) can never stall the whole result set.
        pending = set(futures.keys())
        _drain(pending, _MERGE_BUDGET)

        # Safety net: if we still have nothing (fast providers were slow this
        # time), give the remaining futures a short extra window rather than
        # returning an empty set that a slow provider would have filled.
        if not merged and pending:
            _drain(pending, 2.0)

        # Provider-independent relevance re-ranking. `merged` is already
        # de-duplicated; this pass re-scores by probable user intent and sorts
        # by relevance rather than provider order.
        from .ranking import rank_results
        ranked = rank_results(query, merged)
        return ranked[:limit]

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        Execute a search query with automatic caching.

        Args:
            query: Search query string.
            limit: Maximum results to return.

        Returns:
            List of SearchResult objects.
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Check cache first
        cached = self._cache.get(self._provider_name, query)
        if cached is not None:
            self._last_cached = True
            if _DEBUG:
                print(f'[SEARCH]\nProvider: {self._provider_name} (remembered)\nQuery: "{query}"\nResults: {len(cached)}\n')
            return cached[:limit]

        self._last_cached = False

        # Cache miss — fan out across providers concurrently
        results = self._gather(query, limit=limit)

        # Store in cache (keyed by the configured provider name)
        if results:
            self._cache.put(self._provider_name, query, results)

        return results

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def cache(self) -> SearchCache:
        """Access the cache directly for stats/invalidation."""
        return self._cache

    def close(self):
        """Clean up all providers."""
        self._nsindex.close()
        self._brave.close()
        self._ddg.close()
        self._ddglib.close()
        self._ddgr.close()
        self._fd.close()
        self._rg.close()
        self._pool.shutdown(wait=False)
        if self._provider and hasattr(self._provider, 'close'):
            self._provider.close()
