"""
Raw Response Model
==================
Represents a raw HTTP response from the fetcher.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class RawResponse:
    """
    Raw HTTP response returned by the fetcher.
    """

    url: str = ""
    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    text: str = ""
    content_type: str = ""
    encoding: str = "utf-8"
    redirect_url: Optional[str] = None
    error: Optional[str] = None
    fetch_time_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400 and self.error is None

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower()

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse
        return urlparse(self.url).netloc
