"""
PDF Parser
==========
Parses PDF content into PageDocument.
Requires PyPDF2 or pdfplumber for full functionality.
"""

import re
from ...models.page_document import PageDocument
from ...fetcher.response import RawResponse


class PDFParser:
    """Parses PDF into PageDocument (basic implementation)."""

    def parse(self, response: RawResponse) -> PageDocument:
        doc = PageDocument(url=response.url)
        if not response.ok or not response.content:
            return doc

        try:
            # Try PyPDF2 if available
            import io
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(response.content))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            doc.text = " ".join(text_parts)[:10000]

            # Try to get title from metadata
            if reader.metadata and reader.metadata.title:
                doc.title = reader.metadata.title

        except ImportError:
            # Fallback: extract any readable text
            doc.text = self._extract_text_fallback(response.content)

        import time
        doc.scraped_at = time.time()
        return doc

    def _extract_text_fallback(self, content: bytes) -> str:
        """Basic text extraction from PDF bytes."""
        try:
            text = content.decode("utf-8", errors="ignore")
            # Remove PDF binary junk
            text = re.sub(r"[^\x20-\x7E\n]", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:10000]
        except Exception:
            return ""
