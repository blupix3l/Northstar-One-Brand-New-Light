"""
Index Statistics
================
Exposes comprehensive index statistics for debugging and dashboards.
"""

from typing import Dict, Any
from .indexer import Indexer


class IndexStats:
    """
    Collects and formats index statistics.
    """

    def __init__(self, indexer: Indexer):
        self._indexer = indexer

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self._indexer.stats

        # Add additional computed stats
        store = self._indexer.document_store
        idx = self._indexer.inverted_index

        stats["total_documents"] = store.count
        stats["unique_domains"] = len(store.get_domains())
        stats["unique_languages"] = len(store.get_languages())
        stats["vocabulary_size"] = idx.vocabulary_size
        stats["total_postings"] = idx.total_postings
        stats["total_links"] = self._indexer.link_graph.total_links

        return stats

    def format_stats(self) -> str:
        """Format statistics as readable string."""
        stats = self.get_stats()
        lines = [
            "=== NSIndex Statistics ===",
            f"Documents Indexed:    {stats.get('documents_indexed', 0)}",
            f"Documents Stored:     {stats.get('documents_stored', 0)}",
            f"Vocabulary Size:      {stats.get('vocabulary_size', 0)}",
            f"Total Postings:       {stats.get('total_postings', 0)}",
            f"Total Tokens:         {stats.get('total_tokens', 0)}",
            f"Avg Tokens/Doc:       {stats.get('avg_tokens_per_doc', 0)}",
            f"Duplicate Pages:      {stats.get('duplicates_skipped', 0)}",
            f"Languages:            {stats.get('unique_languages', 0)}",
            f"Domains:              {stats.get('unique_domains', 0)}",
            f"Total Links:          {stats.get('total_links', 0)}",
            "========================",
        ]
        return "\n".join(lines)

    def log_stats(self):
        """Print formatted statistics."""
        print(self.format_stats())
