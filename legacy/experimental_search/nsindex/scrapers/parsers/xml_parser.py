"""
XML Parser
==========
Parses XML content into PageDocument.
"""

import re
from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class XMLParser:
    """Parses XML into PageDocument."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.text:
            return doc

        xml = response.text
        doc.text = xml[:10000]

        # Extract title from <title> tag
        title_match = re.search(r"<title[^>]*>(.*?)</title>", xml, re.DOTALL | re.IGNORECASE)
        doc.title = title_match.group(1).strip() if title_match else ""

        # Extract description
        desc_match = re.search(r"<description[^>]*>(.*?)</description>", xml, re.DOTALL | re.IGNORECASE)
        doc.description = desc_match.group(1).strip() if desc_match else ""

        # Extract links from <loc> tags
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", xml, re.IGNORECASE)
        doc.links = [loc.strip() for loc in locs if loc.strip().startswith("http")]

        import time
        doc.scraped_at = time.time()
        return doc
