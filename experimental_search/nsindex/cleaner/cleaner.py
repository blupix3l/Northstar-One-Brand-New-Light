"""
Content Cleaner
===============
Removes noise from extracted text.
"""

import re
from typing import List


class ContentCleaner:
    """
    Cleans extracted text content.
    Removes navigation, ads, repeated whitespace, etc.
    """

    # Common noise patterns
    NOISE_PATTERNS = [
        r"cookie[s]?\s+policy",
        r"accept\s+all",
        r"reject\s+all",
        r"sign\s+up",
        r"log\s+in",
        r"subscribe\s+now",
        r"click\s+here",
        r"read\s+more",
        r"loading\.\.\.",
        r"advertisement",
        r"sponsored",
        r"promoted",
    ]

    def clean_text(self, text: str) -> str:
        """Clean raw text content."""
        if not text:
            return ""

        # Remove noise phrases
        for pattern in self.NOISE_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove very short fragments (likely navigation)
        words = text.split()
        if len(words) < 5:
            return ""

        return text

    def clean_headings(self, headings: List[str]) -> List[str]:
        """Clean and deduplicate headings."""
        seen = set()
        cleaned = []
        for h in headings:
            h = h.strip()
            if h and h.lower() not in seen and len(h) > 3:
                seen.add(h.lower())
                cleaned.append(h)
        return cleaned

    def clean_links(self, links: List[str], base_domain: str = "") -> List[str]:
        """Clean and filter links."""
        cleaned = []
        for link in links:
            link = link.strip()
            if not link or not link.startswith("http"):
                continue
            # Skip social media share links
            if any(x in link.lower() for x in ["facebook.com/share", "twitter.com/intent", "linkedin.com/share"]):
                continue
            cleaned.append(link)
        return cleaned
