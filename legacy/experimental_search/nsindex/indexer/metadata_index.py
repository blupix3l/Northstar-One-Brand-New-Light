"""
Metadata Index
==============
Indexes document metadata for fast filtering.
"""

from typing import Dict, Set, List
from ..models.page_document import PageDocument


class MetadataIndex:
    """
    Indexes metadata fields for fast lookup.
    """

    def __init__(self):
        self._domain_index: Dict[str, Set[str]] = {}  # domain → doc_ids
        self._language_index: Dict[str, Set[str]] = {}  # language → doc_ids

    def add_document(self, doc_id: str, doc: PageDocument):
        """Index a document's metadata."""
        # Domain index
        if doc.domain:
            if doc.domain not in self._domain_index:
                self._domain_index[doc.domain] = set()
            self._domain_index[doc.domain].add(doc_id)

        # Language index
        if doc.language:
            lang = doc.language.lower()
            if lang not in self._language_index:
                self._language_index[lang] = set()
            self._language_index[lang].add(doc_id)

    def remove_document(self, doc_id: str, doc: PageDocument):
        """Remove a document from all indexes."""
        if doc.domain and doc.domain in self._domain_index:
            self._domain_index[doc.domain].discard(doc_id)
        if doc.language:
            lang = doc.language.lower()
            if lang in self._language_index:
                self._language_index[lang].discard(doc_id)

    def search_by_domain(self, domain: str) -> Set[str]:
        """Get all document IDs for a domain."""
        return self._domain_index.get(domain.lower(), set())

    def search_by_language(self, language: str) -> Set[str]:
        """Get all document IDs for a language."""
        return self._language_index.get(language.lower(), set())

    def clear(self):
        self._domain_index.clear()
        self._language_index.clear()
