"""
Generic Scraper
===============
Default scraper for any HTML page.
"""

import re
from .base import BaseScraper
from ..models.page_document import PageDocument
from ..fetcher.response import RawResponse


class GenericScraper(BaseScraper):
    """
    Generic HTML scraper that extracts basic page information.
    Used as fallback for any site without a specific scraper.
    """

    name = "generic"

    def can_handle(self, url: str) -> bool:
        return True

    def extract(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)

        if not response.ok or not response.text:
            return doc

        html = response.text

        # ── Title ──────────────────────────────────────────────────────────
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        doc.title = title_match.group(1).strip() if title_match else ""

        # ── Description ────────────────────────────────────────────────────
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
                html, re.IGNORECASE
            )
        doc.description = desc_match.group(1).strip() if desc_match else ""

        # ── Headings ───────────────────────────────────────────────────────
        headings = re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.DOTALL | re.IGNORECASE)
        doc.headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings if h.strip()]

        # ── Text Content ───────────────────────────────────────────────────
        # Remove scripts and styles
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        doc.text = clean[:10000]  # Limit text length

        # ── Links ──────────────────────────────────────────────────────────
        links = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        doc.links = [l for l in links if l.startswith("http")]

        # ── Images ─────────────────────────────────────────────────────────
        images = re.findall(r'src=["\']([^"\']+\.(jpg|jpeg|png|gif|webp|svg))["\']', html, re.IGNORECASE)
        doc.images = [img[0] for img in images]

        # ── Language ───────────────────────────────────────────────────────
        lang_match = re.search(r'<html[^>]+lang=["\']([^"\']+)["\']', html, re.IGNORECASE)
        doc.language = lang_match.group(1) if lang_match else ""

        # ── Metadata ───────────────────────────────────────────────────────
        meta_tags = re.findall(
            r'<meta[^>]+name=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE
        )
        doc.metadata = {name: content for name, content in meta_tags}

        doc.scraped_at = __import__("time").time()
        return doc
