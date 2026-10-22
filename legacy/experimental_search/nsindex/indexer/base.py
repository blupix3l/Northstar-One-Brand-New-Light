"""
Base Indexer Interface
======================
Abstract interface for future parallel indexer implementations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from ..models.page_document import PageDocument


class BaseIndexer(ABC):
    """
    Abstract interface for indexers.
    Future implementations: parallel, distributed, incremental.
    """

    @abstractmethod
    def index_document(self, doc: PageDocument, force: bool = False) -> Optional[int]:
        """Index a single document. Returns doc_id or None if skipped."""
        pass

    @abstractmethod
    def index_batch(self, documents: List[PageDocument], force: bool = False) -> Dict[str, int]:
        """Index multiple documents. Returns {url: doc_id}."""
        pass

    @abstractmethod
    def remove_document(self, url: str) -> bool:
        """Remove a document by URL."""
        pass

    @property
    @abstractmethod
    def stats(self) -> dict:
        """Index statistics."""
        pass
