"""NSIndex Search — Query processing and ranking."""

from .query_parser import QueryParser, ParsedQuery
from .ranking import Ranker
from .bm25 import BM25Ranker
from .search_engine import SearchEngine
from .results import SearchResult
from .snippet import SnippetGenerator
from .cache import ResultCache
from .analytics import SearchAnalytics
from .authority import DomainAuthority
from .highlight import SearchHighlighter

__all__ = [
    "QueryParser", "ParsedQuery",
    "Ranker", "BM25Ranker",
    "SearchEngine", "SearchResult",
    "SnippetGenerator", "ResultCache",
    "SearchAnalytics", "DomainAuthority",
    "SearchHighlighter",
]
