"""
Document Store
==============
Stores and retrieves PageDocument objects using integer DocIDs.
"""

from typing import Dict, Optional, List, Set
from ..models.page_document import PageDocument


class DocumentStore:
    """
    In-memory store for PageDocuments.
    Maps integer doc_id → PageDocument.
    """

    def __init__(self):
        self._documents: Dict[int, PageDocument] = {}
        self._url_to_id: Dict[str, int] = {}
        self._hash_to_id: Dict[str, int] = {}
        self._next_id: int = 1

    def add(self, doc: PageDocument) -> int:
        """
        Add a document and return its unique integer ID.
        If URL already exists, returns existing ID.
        """
        # Check if URL already indexed
        if doc.url in self._url_to_id:
            return self._url_to_id[doc.url]

        # Assign new ID
        doc_id = self._next_id
        self._next_id += 1

        doc.doc_id = doc_id
        self._documents[doc_id] = doc
        self._url_to_id[doc.url] = doc_id

        if doc.content_hash:
            self._hash_to_id[doc.content_hash] = doc_id

        return doc_id

    def get(self, doc_id: int) -> Optional[PageDocument]:
        """Retrieve a document by integer ID."""
        return self._documents.get(doc_id)

    def get_by_url(self, url: str) -> Optional[PageDocument]:
        """Retrieve a document by URL."""
        doc_id = self._url_to_id.get(url)
        if doc_id is not None:
            return self._documents.get(doc_id)
        return None

    def get_id_by_url(self, url: str) -> Optional[int]:
        """Get doc_id for a URL."""
        return self._url_to_id.get(url)

    def get_id_by_hash(self, content_hash: str) -> Optional[int]:
        """Get doc_id for a content hash."""
        return self._hash_to_id.get(content_hash)

    def has_url(self, url: str) -> bool:
        """Check if a URL is already stored."""
        return url in self._url_to_id

    def has_hash(self, content_hash: str) -> bool:
        """Check if a content hash is already stored."""
        return content_hash in self._hash_to_id

    def remove(self, doc_id: int) -> bool:
        """Remove a document. Returns True if removed."""
        doc = self._documents.get(doc_id)
        if doc:
            del self._documents[doc_id]
            self._url_to_id.pop(doc.url, None)
            if doc.content_hash:
                self._hash_to_id.pop(doc.content_hash, None)
            return True
        return False

    def search_by_title(self, query: str) -> List[PageDocument]:
        """Find documents with matching title."""
        query_lower = query.lower()
        return [
            doc for doc in self._documents.values()
            if query_lower in doc.title.lower()
        ]

    def get_all_ids(self) -> List[int]:
        """Get all document IDs."""
        return list(self._documents.keys())

    def get_domains(self) -> Set[str]:
        """Get all unique domains."""
        return {doc.domain for doc in self._documents.values() if doc.domain}

    def get_languages(self) -> Set[str]:
        """Get all unique languages."""
        return {doc.language for doc in self._documents.values() if doc.language}

    @property
    def count(self) -> int:
        return len(self._documents)

    def clear(self):
        self._documents.clear()
        self._url_to_id.clear()
        self._hash_to_id.clear()
        self._next_id = 1
