"""
RSS Parser
==========
Parses RSS/Atom feeds into PageDocument.
"""

import re
from typing import List
from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class RSSParser:
    """Parses RSS/Atom feeds into PageDocument."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.text:
            return doc

        xml = response.text
        doc.text = xml[:10000]

        # Feed title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", xml, re.DOTALL | re.IGNORECASE)
        doc.title = title_match.group(1).strip() if title_match else ""

        # Feed description
        desc_match = re.search(r"<description[^>]*>(.*?)</description>", xml, re.DOTALL | re.IGNORECASE)
        doc.description = desc_match.group(1).strip() if desc_match else ""

        # Extract item links
        links = re.findall(r"<link[^>]*>\s*(.*?)\s*</link>", xml, re.DOTALL | re.IGNORECASE)
        doc.links = [l.strip() for l in links if l.strip().startswith("http")]

        # Also check href attributes
        href_links = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', xml, re.IGNORECASE)
        doc.links.extend([l for l in href_links if l.startswith("http")])

        import time
        doc.scraped_at = time.time()
        return doc
