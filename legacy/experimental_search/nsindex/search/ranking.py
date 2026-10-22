"""
Ranker
======
Scores and ranks search results with multiple signals.
"""

import math
from typing import List, Dict, Tuple, Optional, Set
from ..indexer.inverted_index import PostingEntry
from ..indexer.document_store import DocumentStore
from ..indexer.link_graph import LinkGraph
from ..models.page_document import PageDocument


class Ranker:
    """
    Ranks documents based on multiple relevance signals.
    
    Signals:
        - Term frequency (log-scaled)
        - Title match boost
        - Heading match boost
        - Exact phrase boost
        - URL keyword boost
        - Shorter URL bonus
        - Document length normalization
        - Multiple query term bonus
        - Link popularity (future: PageRank)
    """

    def __init__(self, document_store: DocumentStore, link_graph: LinkGraph = None):
        self._doc_store = document_store
        self._link_graph = link_graph

    def rank(self, query_tokens: List[str],
             postings: Dict[str, List[PostingEntry]],
             phrase_doc_ids: Set[int] = None) -> List[Tuple[int, float]]:
        """
        Rank documents based on query tokens and their postings.
        Returns list of (doc_id, score) sorted by score descending.
        """
        phrase_doc_ids = phrase_doc_ids or set()
        doc_scores: Dict[int, float] = {}

        # Score each query token
        for token in query_tokens:
            entries = postings.get(token, [])
            for entry in entries:
                score = self._compute_token_score(entry, len(query_tokens))
                doc_scores[entry.doc_id] = doc_scores.get(entry.doc_id, 0) + score

        # Apply phrase boost
        for doc_id in phrase_doc_ids:
            if doc_id in doc_scores:
                doc_scores[doc_id] *= 2.5

        # Apply document-level boosts
        for doc_id in list(doc_scores.keys()):
            doc = self._doc_store.get(doc_id)
            if doc:
                # URL keyword boost
                url_score = self._url_keyword_score(doc, query_tokens)
                doc_scores[doc_id] += url_score

                # Shorter URL bonus
                url_len = len(doc.url)
                if url_len < 50:
                    doc_scores[doc_id] *= 1.1
                elif url_len > 200:
                    doc_scores[doc_id] *= 0.9

                # Document length normalization
                word_count = doc.word_count()
                if word_count > 0:
                    doc_scores[doc_id] *= 1.0 / math.log2(max(word_count, 10))

        # Apply link popularity boost
        if self._link_graph:
            for doc_id in list(doc_scores.keys()):
                incoming = self._link_graph.incoming_count(doc_id)
                if incoming > 0:
                    doc_scores[doc_id] *= 1.0 + math.log2(incoming) * 0.1

        # Sort by score descending
        ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked

    def _compute_token_score(self, entry: PostingEntry, query_length: int) -> float:
        """Compute relevance score for a single token posting."""
        score = 0.0

        # Frequency score (log-scaled)
        score += 1.0 + math.log2(max(entry.frequency, 1)) * 0.5

        # Title boost (strong signal)
        if entry.in_title:
            score *= 3.0

        # Heading boost
        if entry.in_heading:
            score *= 2.0

        # Position boost (earlier = better)
        if entry.positions:
            avg_pos = sum(entry.positions) / len(entry.positions)
            if avg_pos < 5:
                score *= 1.3

        # Normalize by query length
        score /= max(1, query_length)

        return score

    def _url_keyword_score(self, doc: PageDocument, query_tokens: List[str]) -> float:
        """Boost score if query tokens appear in the URL."""
        score = 0.0
        url_lower = doc.url.lower()
        for token in query_tokens:
            if token.lower() in url_lower:
                score += 0.5
        return score

    def rank_by_domain(self, results: List[Tuple[int, float]],
                       preferred_domains: List[str] = None) -> List[Tuple[int, float]]:
        """Boost results from preferred domains."""
        if not preferred_domains:
            return results

        preferred_set = set(d.lower() for d in preferred_domains)
        boosted = []
        for doc_id, score in results:
            doc = self._doc_store.get(doc_id)
            if doc and doc.domain.lower() in preferred_set:
                score *= 1.5
            boosted.append((doc_id, score))

        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted
