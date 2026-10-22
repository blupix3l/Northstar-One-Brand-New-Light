"""
Brave Search Provider
=====================
Uses the official Brave Search API.
"""

import os
import time
import requests
from typing import List
from ..provider import SearchProvider
from ..models import SearchResult


class BraveSearchProvider(SearchProvider):
    """Search provider using the Brave Search API."""

    name = "brave"
    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str = None, timeout: int = 10):
        self.api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY", "")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        })

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        if not self.api_key:
            print("[SEARCH] Brave: No API key configured")
            return []

        headers = {"X-Subscription-Token": self.api_key}

        start = time.perf_counter()
        try:
            resp = self._session.get(
                self.API_URL,
                params={"q": query, "count": limit},
                headers=headers,
                timeout=self.timeout,
            )
            network_ms = (time.perf_counter() - start) * 1000

            if resp.status_code == 401:
                print("[SEARCH] Brave: Invalid API key")
                return []
            if resp.status_code == 429:
                print("[SEARCH] Brave: Rate limited")
                return []
            if resp.status_code != 200:
                print(f"[SEARCH] Brave: HTTP {resp.status_code}")
                return []

            data = resp.json()
            results = []

            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    display_url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    favicon=item.get("thumbnail", {}).get("src") if item.get("thumbnail") else None,
                    source=self.name,
                ))

            print(f'[SEARCH]\nProvider: Brave\nQuery: "{query}"\n'
                  f'Network Time: {network_ms:.0f} ms\nResults: {len(results)}\n')

            return results[:limit]

        except requests.Timeout:
            print("[SEARCH] Brave: Request timed out")
            return []
        except requests.ConnectionError:
            print("[SEARCH] Brave: Connection failed")
            return []
        except Exception as e:
            print(f"[SEARCH] Brave: {e}")
            return []

    def close(self):
        self._session.close()
