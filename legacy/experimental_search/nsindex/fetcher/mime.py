"""
MIME Detection
==============
Detects content types from HTTP responses.
"""

import re
from typing import Optional


class MIMEDetector:
    """
    Detects MIME types from Content-Type headers and file extensions.
    """

    EXTENSION_MAP = {
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".xml": "application/xml",
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".rss": "application/rss+xml",
        ".atom": "application/atom+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }

    PARSABLE_TYPES = {
        "text/html",
        "application/xhtml+xml",
        "text/markdown",
        "text/plain",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
        "application/json",
    }

    @staticmethod
    def detect(content_type: str, url: str = "") -> str:
        """Detect MIME type from Content-Type header and URL."""
        # Try Content-Type first
        if content_type:
            # Remove parameters (e.g., charset)
            mime = content_type.split(";")[0].strip().lower()
            if mime:
                return mime

        # Try file extension
        if url:
            from urllib.parse import urlparse
            path = urlparse(url).path.lower()
            for ext, mime in MIMEDetector.EXTENSION_MAP.items():
                if path.endswith(ext):
                    return mime

        return "application/octet-stream"

    @staticmethod
    def is_parsable(content_type: str) -> bool:
        """Check if this MIME type can be parsed."""
        mime = content_type.split(";")[0].strip().lower()
        return mime in MIMEDetector.PARSABLE_TYPES

    @staticmethod
    def get_parser_hint(content_type: str) -> str:
        """Get a hint for which parser to use."""
        mime = content_type.split(";")[0].strip().lower()
        if "html" in mime:
            return "html"
        elif "markdown" in mime:
            return "markdown"
        elif "plain" in mime:
            return "text"
        elif "xml" in mime or "rss" in mime or "atom" in mime:
            return "xml"
        elif "json" in mime:
            return "json"
        elif "pdf" in mime:
            return "pdf"
        return "generic"
