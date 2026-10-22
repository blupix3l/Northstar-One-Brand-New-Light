"""
Text Normalizer
===============
Text normalization for indexing.
"""

import re
import unicodedata


class TextNormalizer:
    """
    Normalizes text for consistent indexing.
    """

    # Common English stopwords (minimal set for performance)
    STOPWORDS = frozenset({
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "its", "this", "that",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "can", "shall", "not", "no", "nor", "so", "if", "then",
        "than", "too", "very", "just", "about", "above", "after", "again",
        "all", "also", "any", "as", "because", "before", "between", "both",
        "each", "few", "more", "most", "other", "some", "such", "into",
        "only", "own", "same", "through", "during", "out", "up", "down",
    })

    def normalize(self, text: str, remove_stopwords: bool = False) -> str:
        """Normalize text for indexing."""
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Normalize unicode
        text = unicodedata.normalize("NFKD", text)

        # Remove punctuation (keep alphanumeric and spaces)
        text = re.sub(r"[^\w\s]", " ", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Remove stopwords
        if remove_stopwords:
            words = text.split()
            words = [w for w in words if w not in self.STOPWORDS and len(w) > 1]
            text = " ".join(words)

        return text
