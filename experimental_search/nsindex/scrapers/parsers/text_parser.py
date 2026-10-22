"""
Text Parser
===========
Parses plain text content into PageDocument.
"""

from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class TextParser:
    """Parses plain text into PageDocument."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.text:
            return doc

        doc.text = response.text[:10000]

        # Use first line as title if short enough
        lines = response.text.strip().split("\n")
        if lines and len(lines[0]) < 100:
            doc.title = lines[0].strip()

        import time
        doc.scraped_at = time.time()
        return doc
