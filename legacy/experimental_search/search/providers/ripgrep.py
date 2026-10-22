"""
ripgrep (rg) Provider
=====================
Optional provider that searches file *contents* using the `rg` CLI and
returns matching files with a short snippet of the matched line.

Results are tagged "Local Code" when the matched file looks like source
code (a known code extension), otherwise "Local Content". URLs use the
file:// scheme so they never collide with web results.

Auto-detected via shutil.which("rg"); silently disabled when absent.
"""

import os
import shutil
import subprocess
import time
from typing import List

from ..provider import SearchProvider
from ..models import SearchResult

_LOCAL_ROOT = os.environ.get("NS_LOCAL_SEARCH_ROOT") or os.path.expanduser("~")
_LOCAL_MAX = int(os.environ.get("NS_LOCAL_SEARCH_MAX", "20"))

# Extensions treated as source code for the "Local Code" label.
_CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".cc", ".h",
    ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts",
    ".scala", ".m", ".mm", ".sh", ".bash", ".zsh", ".ps1", ".sql", ".html",
    ".css", ".scss", ".less", ".vue", ".r", ".lua", ".pl", ".vim", ".el",
    ".asm", ".s", ".json", ".yaml", ".yml", ".toml", ".xml",
}


class RipGrepProvider(SearchProvider):
    """Local content/code search using the `rg` CLI."""

    name = "Local Code"

    def __init__(self, timeout: int = 5, root: str = None, max_results: int = None):
        self.timeout = timeout
        self.root = root or _LOCAL_ROOT
        self.max_results = max_results or _LOCAL_MAX
        self.executable = shutil.which("rg")
        self.available = bool(self.executable)

    def _tag_for(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        return "Local Code" if ext in _CODE_EXTS else "Local Content"

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.available or not self.executable:
            return []
        start = time.perf_counter()
        cap = min(limit, self.max_results)
        results: List[SearchResult] = []
        try:
            proc = subprocess.run(
                [self.executable, "--max-count", "1", "--max-filesize", "5M",
                 "-m", str(cap), "--with-filename", "--no-heading",
                 "--line-number", "--color", "never", query, self.root],
                capture_output=True,
                timeout=self.timeout,
            )
            if proc.returncode not in (0, 1):  # rg uses 1 when no matches
                return []
            out = (proc.stdout or b"").decode("utf-8", errors="replace")
            for line in out.splitlines():
                # Format: <path>:<lineno>:<content>
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                path, _lineno, content = parts[0], parts[1], parts[2]
                if not os.path.isabs(path):
                    continue
                url = "file:///" + path.lstrip("/")
                results.append(SearchResult(
                    title=os.path.basename(path) or path,
                    url=url,
                    snippet=content.strip()[:200],
                    source=self._tag_for(path),
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
