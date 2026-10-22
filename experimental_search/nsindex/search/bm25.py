"""
BM25 Ranker
===========
BM25 ranking algorithm implementation.
Primary ranking algorithm with existing boosts preserved.
"""

import math
from typing import List, Dict, Tuple, Set, Optional
from ..indexer.inverted_index import PostingEntry
from ..indexer.document_store import DocumentStore
from ..indexer.link_graph import LinkGraph
from .authority import DomainAuthority


class BM25Ranker:
    """
    BM25 ranking with additional boosts.
    
    BM25 Formula:
        score(q, d) = Σ IDF(qi) * (f(qi,d) * (k1 + 1)) / (f(qi,d) + k1 * (1 - b + b * |d| / avgdl))
    
    Additional boosts:
        - Title match
        - Heading match
        - Exact phrase
        - URL keywords
        - Domain authority
        - Link popularity
    """

    def __init__(self, document_store: DocumentStore,
                 link_graph: LinkGraph = None,
                 authority: DomainAuthority = None,
                 k1: float = 1.5, b: float = 0.75):
        self._doc_store = document_store
        self._link_graph = link_graph
        self._authority = authority or DomainAuthority()
        self._k1 = k1
        self._b = b

        # Precomputed statistics
        self._avg_doc_length = 0.0
        self._doc_count = 0
        self._doc_lengths: Dict[int, int] = {}

    def update_statistics(self, doc_lengths: Dict[int, int]):
        """Update average document length for BM25 normalization."""
        self._doc_lengths = doc_lengths
        self._doc_count = len(doc_lengths)
        if self._doc_count > 0:
            self._avg_doc_length = sum(doc_lengths.values()) / self._doc_count
        else:
            self._avg_doc_length = 1.0

    def rank(self, query_tokens: List[str],
             postings: Dict[str, List[PostingEntry]],
             phrase_doc_ids: Set[int] = None,
             phrase_tokens: List[List[str]] = None) -> List[Tuple[int, float]]:
        """
        Rank documents using BM25 with additional boosts.
        Returns list of (doc_id, score) sorted by score descending.
        """
        phrase_doc_ids = phrase_doc_ids or set()
        doc_scores: Dict[int, float] = {}

        # BM25 scoring
        for token in query_tokens:
            token_lower = token.lower()
            entries = postings.get(token_lower, [])
            if not entries:
                continue

            # IDF calculation
            df = len(entries)
            idf = math.log((self._doc_count - df + 0.5) / (df + 0.5) + 1.0)

            for entry in entries:
                doc_id = entry.doc_id
                tf = entry.frequency
                doc_len = self._doc_lengths.get(doc_id, self._avg_doc_length)

                # BM25 term frequency normalization
                numerator = tf * (self._k1 + 1)
                denominator = tf + self._k1 * (1.0 - self._b + self._b * doc_len / self._avg_doc_length)
                score = idf * (numerator / denominator)

                # Title boost
                if entry.in_title:
                    score *= 2.5

                # Heading boost
                if entry.in_heading:
                    score *= 1.8

                doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + score

        # Phrase boost
        for doc_id in phrase_doc_ids:
            if doc_id in doc_scores:
                doc_scores[doc_id] *= 2.0

        # Document-level boosts
        for doc_id in list(doc_scores.keys()):
            doc = self._doc_store.get(doc_id)
            if not doc:
                continue

            # URL keyword boost
            url_score = 0.0
            for token in query_tokens:
                if token.lower() in doc.url.lower():
                    url_score += 0.3
            doc_scores[doc_id] += url_score

            # Shorter URL bonus
            url_len = len(doc.url)
            if url_len < 50:
                doc_scores[doc_id] *= 1.05
            elif url_len > 200:
                doc_scores[doc_id] *= 0.95

            # Domain authority boost
            authority_boost = self._authority.boost_for_query(doc.domain)
            doc_scores[doc_id] *= authority_boost

            # Link popularity boost
            if self._link_graph:
                incoming = self._link_graph.incoming_count(doc_id)
                if incoming > 0:
                    doc_scores[doc_id] *= 1.0 + math.log2(incoming) * 0.05

        # Sort by score descending
        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
