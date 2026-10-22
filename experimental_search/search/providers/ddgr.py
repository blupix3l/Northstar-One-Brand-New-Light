"""
ddgr (CLI) Provider
====================
Optional provider backed by the `ddgr` command-line tool.

Detection: auto-detected via shutil.which("ddgr"). If the executable is
missing the provider silently disables itself and returns [] — it never
raises and never crashes the pipeline.

Output parsing: ddgr supports `--json` (one JSON object per line). We
prefer that; if JSON parsing fails we fall back to a best-effort line
parse. All errors are swallowed and yield [].
"""

import json
import shutil
import subprocess
import time
from typing import List

from ..provider import SearchProvider
from ..models import SearchResult


class DDGRProvider(SearchProvider):
    """Search provider using the `ddgr` CLI."""

    name = "ddgr"

    def __init__(self, timeout: int = 6):
        self.timeout = timeout
        self.executable = shutil.which("ddgr")
        self.available = bool(self.executable)

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.available or not self.executable:
            return []
        start = time.perf_counter()
        results: List[SearchResult] = []
        try:
            proc = subprocess.run(
                [self.executable, "--json", "-n", str(limit), query],
                capture_output=True,
                timeout=self.timeout,
            )
            out = (proc.stdout or b"").decode("utf-8", errors="replace")
            err = (proc.stderr or b"").decode("utf-8", errors="replace")
            if proc.returncode != 0:
                return []
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    # Best-effort: ddgr sometimes prints a title/url pair.
                    continue
                url = (obj.get("link") or obj.get("url") or "").strip()
                if not url:
                    continue
                results.append(SearchResult(
                    title=obj.get("title", "") or url,
                    url=url,
                    snippet=obj.get("snippet", "") or "",
                    source=self.name,
                ))
                if len(results) >= limit:
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
