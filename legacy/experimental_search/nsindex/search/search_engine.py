"""
Search Engine (Phase 3)
=======================
Production-ready search with BM25, caching, analytics, and snippets.
"""

import time
from typing import List, Dict, Any, Optional, Set
from ..models.page_document import PageDocument
from ..indexer.indexer import Indexer
from .query_parser import QueryParser, ParsedQuery
from .bm25 import BM25Ranker
from .snippet import SnippetGenerator
from .results import SearchResult
from .cache import ResultCache
from .analytics import SearchAnalytics, SearchMetrics
from .authority import DomainAuthority


class SearchEngine:
    """
    Production-ready search engine.
    
    Pipeline:
        Query → Parser → Tokenizer → Index Lookup → BM25 Ranking → Snippets → Results
    
    Features:
        - BM25 ranking with boosts
        - Phrase search
        - Prefix search (autocomplete)
        - Metadata filters
        - Result caching
        - Search analytics
        - Snippet generation
    """

    def __init__(self, indexer: Indexer = None):
        self.indexer = indexer or Indexer()
        self.query_parser = QueryParser()
        self.authority = DomainAuthority()
        self.ranker = BM25Ranker(
            self.indexer.document_store,
            self.indexer.link_graph,
            self.authority,
        )
        self.snippet_gen = SnippetGenerator()
        self.cache = ResultCache()
        self.analytics = SearchAnalytics()

        # Update BM25 statistics
        self._update_bm25_stats()

    def _update_bm25_stats(self):
        """Update BM25 average document length."""
        doc_lengths = {}
        for doc_id in self.indexer.document_store.get_all_ids():
            doc = self.indexer.document_store.get(doc_id)
            if doc:
                doc_lengths[doc_id] = doc.word_count()
        self.ranker.update_statistics(doc_lengths)

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        Search for documents matching the query.
        Returns ranked list of SearchResult objects.
        """
        start = time.perf_counter()

        # Check cache
        cached = self.cache.get(query, limit)
        if cached is not None:
            metrics = SearchMetrics(
                query=query,
                total_time_ms=(time.perf_counter() - start) * 1000,
                results_count=len(cached),
                cache_hit=True,
            )
            self.analytics.record_search(metrics)
            return cached

        # Parse query
        parse_start = time.perf_counter()
        parsed = self.query_parser.parse(query)
        parse_time = (time.perf_counter() - parse_start) * 1000

        # Handle prefix search (autocomplete)
        if parsed.prefix:
            results = self._search_prefix(parsed.prefix, limit)
            self.cache.put(query, results, limit)
            metrics = SearchMetrics(
                query=query,
                total_time_ms=(time.perf_counter() - start) * 1000,
                results_count=len(results),
                cache_hit=False,
            )
            self.analytics.record_search(metrics)
            return results

        # Collect all search tokens
        all_tokens = list(parsed.tokens)
        for phrase in parsed.phrases:
            all_tokens.extend(phrase)

        if not all_tokens and not parsed.filters:
            return []

        # Look up in inverted index
        postings = self.indexer.inverted_index.search_multiple(all_tokens)

        # Get phrase document IDs
        phrase_doc_ids: Set[int] = set()
        for phrase in parsed.phrases:
            docs = self.indexer.inverted_index.get_phrase_docs(phrase)
            phrase_doc_ids.update(docs)

        # BM25 ranking
        rank_start = time.perf_counter()
        ranked = self.ranker.rank(parsed.tokens or all_tokens, postings, phrase_doc_ids)
        rank_time = (time.perf_counter() - rank_start) * 1000

        # Apply metadata filters
        if parsed.filters:
            ranked = self._apply_filters(ranked, parsed.filters)

        # Generate rich results with snippets
        snippet_start = time.perf_counter()
        results = []
        for i, (doc_id, score) in enumerate(ranked[:limit]):
            doc = self.indexer.document_store.get(doc_id)
            if doc:
                snippet = self.snippet_gen.generate(
                    doc.text, parsed.tokens or all_tokens, doc.description
                )
                result = SearchResult(
                    title=doc.title,
                    url=doc.url,
                    domain=doc.domain,
                    snippet=snippet,
                    language=doc.language,
                    content_length=doc.word_count(),
                    last_indexed=doc.indexed_at,
                    score=score,
                    rank=i + 1,
                )
                results.append(result)
        snippet_time = (time.perf_counter() - snippet_start) * 1000

        # Cache results
        self.cache.put(query, results, limit)

        # Record analytics
        total_time = (time.perf_counter() - start) * 1000
        metrics = SearchMetrics(
            query=query,
            total_time_ms=total_time,
            ranking_time_ms=rank_time,
            snippet_time_ms=snippet_time,
            results_count=len(results),
            cache_hit=False,
            documents_searched=self.indexer.document_store.count,
        )
        self.analytics.record_search(metrics)

        print(f'[NSINDEX] Query: "{query}" | Time: {total_time:.1f}ms | Results: {len(results)}')

        return results

    def _search_prefix(self, prefix: str, limit: int) -> List[SearchResult]:
        """Search by token prefix (autocomplete)."""
        matching_ids = self.indexer.inverted_index.search_prefix(prefix, limit)
        results = []
        for doc_id in list(matching_ids)[:limit]:
            doc = self.indexer.document_store.get(doc_id)
            if doc:
                results.append(SearchResult(
                    title=doc.title,
                    url=doc.url,
                    domain=doc.domain,
                    snippet=doc.description[:100] if doc.description else "",
                    language=doc.language,
                    content_length=doc.word_count(),
                    last_indexed=doc.indexed_at,
                    score=1.0,
                    rank=len(results) + 1,
                ))
        return results

    def _apply_filters(self, ranked: List[tuple], filters: Dict[str, str]) -> List[tuple]:
        """Apply metadata filters to ranked results."""
        filtered = []
        for doc_id, score in ranked:
            doc = self.indexer.document_store.get(doc_id)
            if not doc:
                continue

            keep = True
            for key, value in filters.items():
                if key in ("site", "domain"):
                    if value.lower() not in doc.domain.lower():
                        keep = False
                        break
                elif key == "lang":
                    if doc.language.lower() != value.lower():
                        keep = False
                        break
                elif key == "intitle":
                    if value.lower() not in doc.title.lower():
                        keep = False
                        break
                elif key == "url":
                    if value.lower() not in doc.url.lower():
                        keep = False
                        break

            if keep:
                filtered.append((doc_id, score))

        return filtered

    def suggest(self, prefix: str, limit: int = 8) -> List[str]:
        """Generate autocomplete suggestions."""
        return self.indexer.inverted_index.search_prefix(prefix, limit)

    @property
    def stats(self) -> dict:
        return {
            **self.indexer.stats,
            "cache": self.cache.stats(),
            "analytics": self.analytics.get_stats(),
        }
