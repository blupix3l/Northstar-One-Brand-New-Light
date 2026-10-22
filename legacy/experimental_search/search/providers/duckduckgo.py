"""
DuckDuckGo Search Provider
==========================
Uses DuckDuckGo's instant answer API for quick results.
"""

import time
import requests
from typing import List
from ..provider import SearchProvider
from ..models import SearchResult


class DuckDuckGoProvider(SearchProvider):
    """Search provider using DuckDuckGo instant answer API."""

    name = "duckduckgo"
    API_URL = "https://api.duckduckgo.com/"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        })

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        start = time.perf_counter()
        try:
            resp = self._session.get(
                self.API_URL,
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=self.timeout,
            )
            network_ms = (time.perf_counter() - start) * 1000

            # DDG returns 202 for successful queries
            if resp.status_code not in (200, 202):
                print(f"[SEARCH] DuckDuckGo: HTTP {resp.status_code}")
                return []

            data = resp.json()
            results = []

            # Add abstract if available
            abstract_url = data.get("AbstractURL", "")
            abstract = data.get("Abstract", "")
            heading = data.get("Heading", "")
            if abstract_url and abstract:
                results.append(SearchResult(
                    title=heading or query,
                    url=abstract_url,
                    display_url=abstract_url,
                    snippet=abstract[:200],
                    source=self.name,
                    score=10.0,
                ))

            # Add related topics
            for topic in data.get("RelatedTopics", []):
                if "FirstURL" in topic:
                    text = topic.get("Text", "")
                    url = topic.get("FirstURL", "")
                    title = text.split(" - ")[0] if " - " in text else text[:60]
                    snippet = text.split(" - ")[1] if " - " in text else ""

                    results.append(SearchResult(
                        title=title,
                        url=url,
                        display_url=url,
                        snippet=snippet[:200],
                        source=self.name,
                        score=5.0,
                    ))

            print(f'[SEARCH]\nProvider: DuckDuckGo\nQuery: "{query}"\n'
                  f'Network Time: {network_ms:.0f} ms\nResults: {len(results)}\n')

            return results[:limit]

        except requests.Timeout:
            print("[SEARCH] DuckDuckGo: Request timed out")
            return []
        except requests.ConnectionError:
            print("[SEARCH] DuckDuckGo: Connection failed")
            return []
        except Exception as e:
            print(f"[SEARCH] DuckDuckGo: {e}")
            return []

    def close(self):
        self._session.close()
