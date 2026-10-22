"""
fd (local filename search) Provider
====================================
Optional provider that searches filenames on the local filesystem using
the `fd` command. Results are tagged as "Local File" and use a file:// URL
so they never collide with web results in the de-duplication step.

Auto-detected via shutil.which("fd"); silently disabled when absent.
Searches only filenames (no file contents).
"""

import os
import shutil
import subprocess
import time
from typing import List

from ..provider import SearchProvider
from ..models import SearchResult

# Optional scope root + result cap, configurable via environment.
_LOCAL_ROOT = os.environ.get("NS_LOCAL_SEARCH_ROOT") or os.path.expanduser("~")
_LOCAL_MAX = int(os.environ.get("NS_LOCAL_SEARCH_MAX", "20"))


class FdProvider(SearchProvider):
    """Local filename search using the `fd` CLI."""

    name = "Local File"

    def __init__(self, timeout: int = 5, root: str = None, max_results: int = None):
        self.timeout = timeout
        self.root = root or _LOCAL_ROOT
        self.max_results = max_results or _LOCAL_MAX
        self.executable = shutil.which("fd")
        self.available = bool(self.executable)

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.available or not self.executable:
            return []
        start = time.perf_counter()
        cap = min(limit, self.max_results)
        results: List[SearchResult] = []
        try:
            proc = subprocess.run(
                [self.executable, "--max-results", str(cap), "--fixed-strings",
                 query, self.root],
                capture_output=True,
                timeout=self.timeout,
            )
            if proc.returncode not in (0, 1):  # fd uses 1 when no matches
                return []
            out = (proc.stdout or b"").decode("utf-8", errors="replace")
            for line in out.splitlines():
                path = line.strip()
                if not path or not os.path.isabs(path):
                    continue
                url = "file:///" + path.lstrip("/")
                results.append(SearchResult(
                    title=os.path.basename(path) or path,
                    url=url,
                    snippet=path,
                    source=self.name,
                ))
                if len(results) >= cap:
                    break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            results = []
        except Exception:
            results = []
        ms = (time.perf_counter() - start) * 1000
        print(f"[SEARCH] {self.name.ljust(12)} {ms:>7.0f} ms  results={len(results)}")
        return results[:limit]

    def close(self):
        pass
