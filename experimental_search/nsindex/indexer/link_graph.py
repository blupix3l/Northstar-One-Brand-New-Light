"""
Link Graph
==========
Tracks incoming and outgoing links between indexed documents.
Separate from the inverted index — used for future ranking algorithms.
"""

from typing import Dict, Set, List
from collections import defaultdict


class LinkGraph:
    """
    Stores the link structure between indexed documents.
    
    outgoing[doc_id] → set of doc_ids this document links to
    incoming[doc_id] → set of doc_ids that link to this document
    """

    def __init__(self):
        self._outgoing: Dict[int, Set[int]] = defaultdict(set)
        self._incoming: Dict[int, Set[int]] = defaultdict(set)
        self._url_to_id: Dict[str, int] = {}

    def add_link(self, from_id: int, to_id: int):
        """Record a link from one document to another."""
        self._outgoing[from_id].add(to_id)
        self._incoming[to_id].add(from_id)

    def add_links_from_url(self, from_id: int, links: List[str],
                           url_to_id_func):
        """
        Add all outgoing links from a document.
        url_to_id_func: callable that maps URL → doc_id (or None if not indexed).
        """
        for url in links:
            to_id = url_to_id_func(url)
            if to_id is not None and to_id != from_id:
                self.add_link(from_id, to_id)

    def get_outgoing(self, doc_id: int) -> Set[int]:
        """Get document IDs this document links to."""
        return self._outgoing.get(doc_id, set())

    def get_incoming(self, doc_id: int) -> Set[int]:
        """Get document IDs that link to this document."""
        return self._incoming.get(doc_id, set())

    def outgoing_count(self, doc_id: int) -> int:
        return len(self._outgoing.get(doc_id, set()))

    def incoming_count(self, doc_id: int) -> int:
        return len(self._incoming.get(doc_id, set()))

    def remove_document(self, doc_id: int):
        """Remove a document and all its links."""
        # Remove outgoing links
        for to_id in self._outgoing.pop(doc_id, set()):
            self._incoming[to_id].discard(doc_id)

        # Remove incoming links
        for from_id in self._incoming.pop(doc_id, set()):
            self._outgoing[from_id].discard(doc_id)

    def clear(self):
        self._outgoing.clear()
        self._incoming.clear()

    @property
    def total_links(self) -> int:
        return sum(len(ids) for ids in self._outgoing.values())
