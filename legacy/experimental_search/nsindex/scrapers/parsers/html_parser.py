"""
HTML Parser
===========
Parses HTML content into PageDocument.
"""

import re
from typing import List
from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class HTMLParser:
    """Parses HTML content into structured PageDocument."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.text:
            return doc

        html = response.text

        # Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        doc.title = title_match.group(1).strip() if title_match else ""

        # Description
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

        # Canonical URL
        canon_match = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        if canon_match:
            doc.metadata["canonical"] = canon_match.group(1)

        # Headings
        headings = re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.DOTALL | re.IGNORECASE)
        doc.headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings if h.strip()]

        # Text content
        clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<style[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        doc.text = clean[:10000]

        # Links
        links = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        doc.links = [l for l in links if l.startswith("http")]

        # Images
        images = re.findall(r'src=["\']([^"\']+\.(jpg|jpeg|png|gif|webp|svg))["\']', html, re.IGNORECASE)
        doc.images = [img[0] for img in images]

        # Language
        lang_match = re.search(r'<html[^>]+lang=["\']([^"\']+)["\']', html, re.IGNORECASE)
        doc.language = lang_match.group(1) if lang_match else ""

        # Open Graph metadata
        og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if og_title:
            doc.metadata["og:title"] = og_title.group(1)

        og_image = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if og_image:
            doc.metadata["og:image"] = og_image.group(1)

        import time
        doc.scraped_at = time.time()
        return doc
