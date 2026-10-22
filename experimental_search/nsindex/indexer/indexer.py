"""
Indexer (Phase 3)
=================
Production indexer with persistent storage and incremental updates.
"""

import time
from typing import List, Optional, Dict, Set
from ..models.page_document import PageDocument
from ..tokenizer.tokenizer import Tokenizer
from .inverted_index import InvertedIndex
from .document_store import DocumentStore
from .metadata_index import MetadataIndex
from .link_graph import LinkGraph


class Indexer:
    """
    Main indexer with persistent storage support.
    Handles duplicate detection, content hashing, and incremental updates.
    """

    def __init__(self, remove_stopwords: bool = False, storage=None):
        self.tokenizer = Tokenizer(remove_stopwords=remove_stopwords)
        self.inverted_index = InvertedIndex()
        self.document_store = DocumentStore()
        self.metadata_index = MetadataIndex()
        self.link_graph = LinkGraph()
        self._storage = storage

        # Statistics
        self._total_indexed = 0
        self._total_duplicates = 0
        self._total_tokens = 0

        # Load from storage if available
        if storage:
            self._load_from_storage()

    def _load_from_storage(self):
        """Load index from persistent storage into memory."""
        if not self._storage:
            return

        # Load all documents into memory
        rows = self._storage._conn.execute("SELECT * FROM documents").fetchall()
        for row in rows:
            doc = self._storage._row_to_document(row)
            self.document_store.add(doc)
            self.metadata_index.add_document(doc.doc_id, doc)

        # Load postings into inverted index
        posting_rows = self._storage._conn.execute(
            "SELECT token, doc_id, frequency, in_title, in_heading, positions FROM postings"
        ).fetchall()
        for token, doc_id, freq, in_title, in_heading, positions_json in posting_rows:
            import json
            positions = json.loads(positions_json) if positions_json else []
            entry = PostingEntry(
                doc_id=doc_id,
                frequency=freq,
                in_title=bool(in_title),
                in_heading=bool(in_heading),
                positions=positions,
            )
            if token not in self.inverted_index._index:
                self.inverted_index._index[token] = []
            self.inverted_index._index[token].append(entry)

        # Load link graph
        link_rows = self._storage._conn.execute("SELECT from_id, to_id FROM link_graph").fetchall()
        for from_id, to_id in link_rows:
            self.link_graph.add_link(from_id, to_id)

        print(f"[NSINDEX] Loaded {len(rows)} documents, {len(posting_rows)} postings, {len(link_rows)} links from storage")

    def index_document(self, doc: PageDocument, force: bool = False) -> Optional[int]:
        """
        Index a single document.
        Returns the document ID, or None if skipped (duplicate).
        """
        # Compute content hash
        doc.content_hash = doc.compute_content_hash()

        # Duplicate detection by content hash
        if not force and doc.content_hash:
            if self._storage:
                existing_url = self._storage.get_url_by_hash(doc.content_hash)
                if existing_url:
                    self._total_duplicates += 1
                    return None
            elif self.document_store.has_hash(doc.content_hash):
                self._total_duplicates += 1
                return None

        # Duplicate detection by URL
        if not force:
            if self._storage:
                existing = self._storage.get_document_by_url(doc.url)
                if existing and existing.content_hash == doc.content_hash:
                    self._total_duplicates += 1
                    return None
            elif self.document_store.has_url(doc.url):
                existing = self.document_store.get_by_url(doc.url)
                if existing and existing.content_hash == doc.content_hash:
                    self._total_duplicates += 1
                    return None

        # Store document
        if self._storage:
            doc_id = self._storage.store_document(doc)
            doc.doc_id = doc_id
            # Also add to in-memory store for fast lookup
            self.document_store.add(doc)
        else:
            doc_id = self.document_store.add(doc)
        doc.indexed_at = time.time()

        # Tokenize content
        title_tokens = set(self.tokenizer.tokenize(doc.title))
        heading_tokens = set()
        for heading in doc.headings:
            heading_tokens.update(self.tokenizer.tokenize(heading))
        body_tokens = self.tokenizer.tokenize(doc.text)

        # Add to inverted index
        all_tokens = list(title_tokens) + list(heading_tokens) + body_tokens
        self.inverted_index.add_document(
            doc_id=doc_id,
            tokens=all_tokens,
            title_tokens=title_tokens,
            heading_tokens=heading_tokens,
        )

        # Persist postings
        if self._storage:
            freq = {}
            positions = {}
            for i, token in enumerate(all_tokens):
                freq[token] = freq.get(token, 0) + 1
                if token not in positions:
                    positions[token] = []
                positions[token].append(i)
            for token, count in freq.items():
                self._storage.store_postings(
                    doc_id, token, count,
                    token in title_tokens,
                    token in heading_tokens,
                    positions.get(token, [])
                )
            self._storage.commit_postings()

        # Add to metadata index
        self.metadata_index.add_document(doc_id, doc)
        if self._storage:
            self._storage.store_metadata(doc_id, doc.domain, doc.language)

        # Add links to link graph
        if doc.links:
            self.link_graph.add_links_from_url(
                doc_id, doc.links,
                lambda url: self.document_store.get_id_by_url(url) or (
                    self._storage.get_document_by_url(url).doc_id
                    if self._storage and self._storage.has_url(url) else None
                )
            )
            if self._storage:
                for link in doc.links:
                    link_doc = self.document_store.get_by_url(link)
                    if not link_doc and self._storage:
                        link_doc = self._storage.get_document_by_url(link)
                    if link_doc:
                        self._storage.store_link(doc_id, link_doc.doc_id)
                self._storage.commit_links()

        self._total_indexed += 1
        self._total_tokens += len(all_tokens)

        # Persist to storage
        if self._storage:
            self._storage.commit()

        return doc_id

    def index_batch(self, documents: List[PageDocument], force: bool = False) -> Dict[str, int]:
        """Index multiple documents. Returns {url: doc_id}."""
        results = {}
        for doc in documents:
            if doc.is_valid():
                doc_id = self.index_document(doc, force=force)
                if doc_id is not None:
                    results[doc.url] = doc_id
        return results

    def remove_document(self, url: str) -> bool:
        """Remove a document by URL."""
        if self._storage:
            doc = self._storage.get_document_by_url(url)
            if doc:
                self._storage.delete_document(doc.doc_id)
                return True
            return False

        doc = self.document_store.get_by_url(url)
        if doc:
            doc_id = doc.doc_id
            self.inverted_index.remove_document(doc_id)
            self.link_graph.remove_document(doc_id)
            self.metadata_index.remove_document(doc_id, doc)
            self.document_store.remove(doc_id)
            return True
        return False

    def has_content(self, content_hash: str) -> bool:
        """Check if content hash is already indexed."""
        if self._storage:
            return self._storage.has_hash(content_hash)
        return self.document_store.has_hash(content_hash)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "documents_indexed": self._total_indexed,
            "duplicates_skipped": self._total_duplicates,
            "vocabulary_size": self.inverted_index.vocabulary_size,
            "total_postings": self.inverted_index.total_postings,
            "total_tokens": self._total_tokens,
            "avg_tokens_per_doc": (
                self._total_tokens // self._total_indexed
                if self._total_indexed > 0 else 0
            ),
            "documents_stored": self.document_store.count,
            "domains": len(self.document_store.get_domains()),
            "languages": len(self.document_store.get_languages()),
            "total_links": self.link_graph.total_links,
        }
