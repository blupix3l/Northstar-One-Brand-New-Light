"""
Snippet Generator
=================
Generates search result snippets from document content.
"""

import re
from typing import List, Optional


class SnippetGenerator:
    """
    Generates contextual snippets for search results.
    Prefers text surrounding matched query terms.
    """

    def __init__(self, max_length: int = 200):
        self._max_length = max_length

    def generate(self, text: str, query_tokens: List[str],
                 description: str = "") -> str:
        """
        Generate a snippet from document text.
        
        Args:
            text: Full document text.
            query_tokens: Tokens from the search query.
            description: Optional page description fallback.
            
        Returns:
            Snippet string with ellipsis markers.
        """
        if not text:
            return description or ""

        # Try to find text containing query terms
        if query_tokens:
            snippet = self._find_context(text, query_tokens)
            if snippet:
                return snippet

        # Fallback: use description
        if description and len(description) > 20:
            return self._truncate(description)

        # Fallback: first meaningful paragraph
        return self._first_paragraph(text)

    def _find_context(self, text: str, query_tokens: List[str]) -> Optional[str]:
        """Find text surrounding matched query terms."""
        text_lower = text.lower()

        # Find first occurrence of any query token
        best_pos = -1
        for token in query_tokens:
            pos = text_lower.find(token.lower())
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            return None

        # Extract context around the match
        start = max(0, best_pos - 60)
        end = min(len(text), best_pos + self._max_length - 60)

        # Try to break at word boundaries
        if start > 0:
            space = text.rfind(" ", 0, start + 20)
            if space != -1:
                start = space + 1

        if end < len(text):
            space = text.find(" ", end - 20)
            if space != -1:
                end = space

        snippet = text[start:end].strip()

        # Add ellipsis markers
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def _first_paragraph(self, text: str) -> str:
        """Extract the first meaningful paragraph."""
        # Split by double newline or sentence boundary
        paragraphs = re.split(r'\n\s*\n|[.!?]\s+', text)
        for p in paragraphs:
            p = p.strip()
            if len(p) > 20:
                return self._truncate(p)
        return self._truncate(text)

    def _truncate(self, text: str) -> str:
        """Truncate text to max_length with ellipsis."""
        if len(text) <= self._max_length:
            return text
        truncated = text[:self._max_length - 3]
        space = truncated.rfind(" ")
        if space > self._max_length - 40:
            truncated = truncated[:space]
        return truncated + "..."
