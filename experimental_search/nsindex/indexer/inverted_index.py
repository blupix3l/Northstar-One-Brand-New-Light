"""
Inverted Index
==============
Word → Matching Documents mapping using integer DocIDs.
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class PostingEntry:
    """A single entry in the inverted index."""
    doc_id: int
    frequency: int = 0
    in_title: bool = False
    in_heading: bool = False
    positions: List[int] = field(default_factory=list)


class InvertedIndex:
    """
    Inverted index: word → list of PostingEntry.
    
    Uses integer DocIDs instead of full URLs for efficiency.
    """

    def __init__(self):
        self._index: Dict[str, List[PostingEntry]] = {}
        self._prefix_index: Dict[str, Set[int]] = {}  # For prefix search

    def add_document(self, doc_id: int, tokens: List[str],
                     title_tokens: Set[str] = None,
                     heading_tokens: Set[str] = None):
        """Add a document's tokens to the index."""
        title_tokens = title_tokens or set()
        heading_tokens = heading_tokens or set()

        # Count frequencies and positions
        freq: Dict[str, int] = {}
        positions: Dict[str, List[int]] = {}
        for i, token in enumerate(tokens):
            freq[token] = freq.get(token, 0) + 1
            if token not in positions:
                positions[token] = []
            positions[token].append(i)

        # Add to inverted index
        for token, count in freq.items():
            entry = PostingEntry(
                doc_id=doc_id,
                frequency=count,
                in_title=token in title_tokens,
                in_heading=token in heading_tokens,
                positions=positions.get(token, []),
            )
            if token not in self._index:
                self._index[token] = []
            self._index[token].append(entry)

            # Add to prefix index (first 3 chars)
            prefix = token[:3]
            if prefix not in self._prefix_index:
                self._prefix_index[prefix] = set()
            self._prefix_index[prefix].add(doc_id)

    def remove_document(self, doc_id: int):
        """Remove a document from the index."""
        tokens_to_remove = []
        for token, entries in self._index.items():
            self._index[token] = [e for e in entries if e.doc_id != doc_id]
            if not self._index[token]:
                tokens_to_remove.append(token)
        for token in tokens_to_remove:
            del self._index[token]

        # Rebuild prefix index
        self._prefix_index.clear()
        for token, entries in self._index.items():
            prefix = token[:3]
            if prefix not in self._prefix_index:
                self._prefix_index[prefix] = set()
            for entry in entries:
                self._prefix_index[prefix].add(entry.doc_id)

    def search(self, token: str) -> List[PostingEntry]:
        """Find all documents containing an exact token."""
        return self._index.get(token.lower(), [])

    def search_prefix(self, prefix: str, limit: int = 10) -> Set[int]:
        """Find document IDs matching a token prefix (for autocomplete)."""
        prefix = prefix.lower()[:3]
        if len(prefix) < 2:
            return set()

        doc_ids = set()
        for p, ids in self._prefix_index.items():
            if p.startswith(prefix):
                doc_ids.update(ids)
        return doc_ids

    def search_multiple(self, tokens: List[str]) -> Dict[str, List[PostingEntry]]:
        """Search for multiple tokens and return results grouped by token."""
        results = {}
        for token in tokens:
            results[token] = self.search(token)
        return results

    def get_document_ids(self, tokens: List[str]) -> Set[int]:
        """Get all document IDs that contain any of the given tokens."""
        doc_ids = set()
        for token in tokens:
            for entry in self._index.get(token.lower(), []):
                doc_ids.add(entry.doc_id)
        return doc_ids

    def get_phrase_docs(self, tokens: List[str]) -> Set[int]:
        """Find documents containing all tokens as a consecutive phrase."""
        if not tokens:
            return set()

        # Get docs containing the first token
        first_entries = self.search(tokens[0])
        if not first_entries:
            return set()

        # For each candidate, check if remaining tokens appear consecutively
        phrase_docs = set()
        for entry in first_entries:
            if self._has_phrase(entry, tokens):
                phrase_docs.add(entry.doc_id)

        return phrase_docs

    def _has_phrase(self, entry: PostingEntry, tokens: List[str]) -> bool:
        """Check if tokens appear consecutively in a document's positions."""
        if len(tokens) == 1:
            return True

        positions = entry.positions
        for start_pos in positions:
            found = True
            for i, token in enumerate(tokens[1:]):
                next_entries = self.search(token)
                next_doc_entries = [e for e in next_entries if e.doc_id == entry.doc_id]
                if not next_doc_entries:
                    found = False
                    break
                next_positions = next_doc_entries[0].positions
                if (start_pos + i + 1) not in next_positions:
                    found = False
                    break
            if found:
                return True
        return False

    @property
    def vocabulary_size(self) -> int:
        return len(self._index)

    @property
    def total_postings(self) -> int:
        return sum(len(entries) for entries in self._index.values())

    def clear(self):
        self._index.clear()
        self._prefix_index.clear()
