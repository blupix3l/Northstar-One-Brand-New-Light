"""
HTTP Client
===========
Low-level HTTP request handling.
"""

import time
import requests
from typing import Optional
from .response import RawResponse


class HTTPClient:
    """
    Handles HTTP requests with retries, timeouts, and compression.
    """

    DEFAULT_HEADERS = {
        "User-Agent": "NorthStarBot/1.0 (+https://northstar.dev/bot)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }

    def __init__(self, timeout: int = 10, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update(self.DEFAULT_HEADERS)

    def get(self, url: str) -> RawResponse:
        """
        Fetch a URL with retries.
        Returns a RawResponse regardless of success/failure.
        """
        start = time.perf_counter()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                elapsed = (time.perf_counter() - start) * 1000

                # Detect encoding
                encoding = resp.encoding or "utf-8"
                try:
                    text = resp.content.decode(encoding, errors="replace")
                except Exception:
                    text = resp.content.decode("utf-8", errors="replace")

                return RawResponse(
                    url=resp.url,  # Use final URL after redirects
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    content=resp.content,
                    text=text,
                    content_type=resp.headers.get("Content-Type", ""),
                    encoding=encoding,
                    redirect_url=str(resp.url) if resp.url != url else None,
                    fetch_time_ms=elapsed,
                )

            except requests.Timeout:
                last_error = "Timeout"
            except requests.ConnectionError:
                last_error = "Connection failed"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(0.5 * (attempt + 1))

        elapsed = (time.perf_counter() - start) * 1000
        return RawResponse(
            url=url,
            status_code=0,
            error=last_error or "Unknown error",
            fetch_time_ms=elapsed,
        )

    def close(self):
        self._session.close()
