"""
Tokenizer
=========
Converts text into searchable tokens.
"""

from typing import List, Dict, Tuple
from .normalizer import TextNormalizer


class Tokenizer:
    """
    Tokenizes text for indexing.
    Converts "Dogs love dog food" into ["dogs", "love", "dog", "food"].
    """

    def __init__(self, remove_stopwords: bool = False):
        self.normalizer = TextNormalizer()
        self._remove_stopwords = remove_stopwords

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into a list of normalized tokens."""
        if not text:
            return []
        normalized = self.normalizer.normalize(text, self._remove_stopwords)
        return normalized.split() if normalized else []

    def tokenize_with_positions(self, text: str) -> List[Tuple[str, int]]:
        """Tokenize text and return (token, position) pairs."""
        tokens = self.tokenize(text)
        return [(token, i) for i, token in enumerate(tokens)]

    def tokenize_with_frequencies(self, text: str) -> Dict[str, int]:
        """Tokenize text and return token frequency counts."""
        tokens = self.tokenize(text)
        freq: Dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        return freq

    def is_title_token(self, token: str, title: str) -> bool:
        """Check if a token appears in the title."""
        return token.lower() in title.lower()

    def is_heading_token(self, token: str, headings: list) -> bool:
        """Check if a token appears in any heading."""
        return any(token.lower() in h.lower() for h in headings)
