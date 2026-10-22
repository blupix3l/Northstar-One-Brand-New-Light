"""
Search Highlighter
==================
Highlights matched query words in search snippets.
"""

import re
from typing import List


class SearchHighlighter:
    """
    Highlights matched query terms in text.
    """

    @staticmethod
    def highlight(text: str, query_tokens: List[str], marker: str = "<b>", end_marker: str = "</b>") -> str:
        """
        Highlight matched tokens in text.
        Returns HTML-safe highlighted text.
        """
        if not text or not query_tokens:
            return text

        result = text
        for token in query_tokens:
            # Case-insensitive word boundary match
            pattern = re.compile(r'\b(' + re.escape(token) + r')\b', re.IGNORECASE)
            result = pattern.sub(f"{marker}\\1{end_marker}", result)

        return result

    @staticmethod
    def highlight_phrases(text: str, phrases: List[List[str]], marker: str = "<b>", end_marker: str = "</b>") -> str:
        """Highlight exact phrases in text."""
        if not text or not phrases:
            return text

        result = text
        for phrase_tokens in phrases:
            phrase = " ".join(phrase_tokens)
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            result = pattern.sub(f"{marker}\\g<0>{end_marker}", result)

        return result
