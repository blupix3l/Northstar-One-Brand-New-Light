"""
Query Suggestions
=================
Autocomplete from indexed vocabulary.
"""

from typing import List, Set


class QuerySuggester:
    """
    Generates query suggestions from indexed vocabulary.
    Useful for autocomplete functionality.
    """

    def __init__(self, storage=None):
        self._storage = storage
        self._vocabulary_cache: Set[str] = set()

    def load_vocabulary(self, tokens: Set[str]):
        """Load vocabulary from the inverted index."""
        self._vocabulary_cache = tokens

    def suggest(self, prefix: str, limit: int = 8) -> List[str]:
        """
        Generate suggestions for a prefix.
        
        Example:
            "pyth" → ["python", "python3", "python.org"]
        """
        if not prefix or len(prefix) < 2:
            return []

        prefix_lower = prefix.lower()
        suggestions = []

        # Search vocabulary for matching tokens
        for token in self._vocabulary_cache:
            if token.startswith(prefix_lower) and len(token) > len(prefix_lower):
                suggestions.append(token)
                if len(suggestions) >= limit * 2:
                    break

        # Also search from storage if available
        if self._storage:
            try:
                storage_suggestions = self._storage.search_vocabulary(prefix_lower, limit * 2)
                for s in storage_suggestions:
                    if s not in suggestions:
                        suggestions.append(s)
            except Exception:
                pass

        # Sort by length (shorter first) and limit
        suggestions.sort(key=lambda s: (len(s), s))
        return suggestions[:limit]

    def suggest_phrases(self, prefix: str, limit: int = 5) -> List[str]:
        """
        Generate multi-word phrase suggestions.
        Uses common title patterns from indexed documents.
        """
        if not prefix or len(prefix) < 3:
            return []

        # For now, return token suggestions
        # Future: could analyze title patterns for multi-word suggestions
        return self.suggest(prefix, limit)
