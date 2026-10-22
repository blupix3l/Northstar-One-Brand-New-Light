"""
Markdown Parser
===============
Parses Markdown content into PageDocument.
"""

import re
from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class MarkdownParser:
    """Parses Markdown into PageDocument."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.text:
            return doc

        md = response.text
        doc.text = md[:10000]

        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
        if title_match:
            doc.title = title_match.group(1).strip()

        # Extract headings
        headings = re.findall(r"^(#{1,6})\s+(.+)$", md, re.MULTILINE)
        doc.headings = [h[1].strip() for h in headings]

        # Extract links
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", md)
        doc.links = [link[1] for link in links if link[1].startswith("http")]

        import time
        doc.scraped_at = time.time()
        return doc
