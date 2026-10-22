"""
Query Parser
============
Parses search queries into structured form.
Supports: keywords, phrases, prefix, metadata filters.
"""

import re
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from ..tokenizer.tokenizer import Tokenizer


@dataclass
class ParsedQuery:
    """Structured representation of a parsed query."""
    tokens: List[str] = field(default_factory=list)
    phrases: List[List[str]] = field(default_factory=list)
    prefix: str = ""
    filters: Dict[str, str] = field(default_factory=dict)
    exclude_tokens: List[str] = field(default_factory=list)


class QueryParser:
    """
    Parses search queries into tokens, phrases, and filters.
    
    Supports:
        - Keywords: python tutorial
        - Phrases: "dog food"
        - Prefix: pyth*  or  pyth
        - Filters: site:github.com  lang:en
        - Exclusion: -unwanted
    """

    def __init__(self):
        self.tokenizer = Tokenizer()

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a query string into a ParsedQuery object.
        """
        result = ParsedQuery()
        query = query.strip()

        if not query:
            return result

        # Extract quoted phrases
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)
        for phrase in phrases:
            tokens = self.tokenizer.tokenize(phrase)
            if tokens:
                result.phrases.append(tokens)

        # Remove quoted phrases from query for further parsing
        query_no_phrases = re.sub(phrase_pattern, "", query).strip()

        # Extract metadata filters (site:, lang:, etc.)
        filter_pattern = r'(\w+):(\S+)'
        filters = re.findall(filter_pattern, query_no_phrases)
        for key, value in filters:
            if key.lower() in ("site", "lang", "domain", "url", "intitle"):
                result.filters[key.lower()] = value
                query_no_phrases = query_no_phrases.replace(f"{key}:{value}", "").strip()

        # Extract prefix (ends with *)
        if "*" in query_no_phrases:
            prefix_part = query_no_phrases.replace("*", "").strip()
            if prefix_part:
                result.prefix = prefix_part.lower()
            query_no_phrases = query_no_phrases.replace("*", "").strip()

        # Extract exclusion tokens
        exclusion_pattern = r'-(\w+)'
        exclusions = re.findall(exclusion_pattern, query_no_phrases)
        result.exclude_tokens = [e.lower() for e in exclusions]
        query_no_phrases = re.sub(exclusion_pattern, "", query_no_phrases).strip()

        # Extract remaining tokens
        if query_no_phrases:
            # Check for OR
            if " OR " in query_no_phrases.upper():
                parts = re.split(r"\s+OR\s+", query_no_phrases, flags=re.IGNORECASE)
                for part in parts:
                    tokens = self.tokenizer.tokenize(part)
                    result.tokens.extend(tokens)
            else:
                result.tokens = self.tokenizer.tokenize(query_no_phrases)

        return result

    def has_phrase(self, query: ParsedQuery) -> bool:
        """Check if query contains any phrases."""
        return len(query.phrases) > 0

    def has_filters(self, query: ParsedQuery) -> bool:
        """Check if query contains any metadata filters."""
        return len(query.filters) > 0

    def has_prefix(self, query: ParsedQuery) -> bool:
        """Check if query contains a prefix search."""
        return bool(query.prefix)
