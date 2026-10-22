"""
Downloader
==========
High-level download orchestrator.
"""

import time
from typing import Optional, List
from .http_client import HTTPClient
from .response import RawResponse


class Downloader:
    """
    Downloads web pages with politeness and error handling.
    """

    def __init__(self, client: Optional[HTTPClient] = None):
        self._client = client or HTTPClient()
        self._download_count = 0
        self._error_count = 0

    def download(self, url: str) -> RawResponse:
        """
        Download a single URL.
        Returns RawResponse with content or error.
        """
        response = self._client.get(url)
        self._download_count += 1
        if not response.ok:
            self._error_count += 1
        return response

    def download_batch(self, urls: List[str]) -> List[RawResponse]:
        """Download multiple URLs sequentially."""
        return [self.download(url) for url in urls]

    @property
    def stats(self) -> dict:
        return {
            "downloads": self._download_count,
            "errors": self._error_count,
            "success_rate": (
                (self._download_count - self._error_count) / self._download_count
                if self._download_count > 0 else 0
            ),
        }

    def close(self):
        self._client.close()
