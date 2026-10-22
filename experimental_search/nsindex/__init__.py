"""
NSIndex — Modular Search Engine Indexing Pipeline (Phase 4)
===========================================================

Real-world web crawler capable of discovering, crawling, indexing
and maintaining thousands of websites.

Architecture:
    Crawler → Fetcher → Parser → Cleaner → Tokenizer → Indexer → Search

Components:
    - crawler: URL discovery, scheduling, politeness
    - fetcher: HTTP downloading with MIME detection
    - scrapers: Content extraction (pluggable)
    - parsers: MIME-specific content parsers
    - cleaner: Content cleaning
    - tokenizer: Text tokenization
    - indexer: Inverted index with DocIDs, content hashing, link graph
    - search: BM25 ranking, phrases, filters, highlighting
    - storage: Persistent SQLite backend
"""

__version__ = "4.0.0"

# Core models
from .models import PageDocument

# Crawler
from .crawler import URLFrontier, CrawlScheduler, RobotsChecker, SitemapDiscovery, WebCrawler
from .crawler.policies import CrawlPolicy, CrawlPolicyManager
from .crawler.manager import CrawlManager, CrawlJob, JobStatus
from .crawler.seeds import SeedManager, SeedEntry
from .crawler.revisit import RevisitPolicyManager, RevisitSchedule
from .crawler.history import CrawlHistory, CrawlRecord
from .crawler.dashboard import CrawlDashboard
from .crawler.url_scorer import URLScorer
from .crawler.url_utils import URLNormalizer

# Fetcher
from .fetcher import HTTPClient, Downloader, RawResponse
from .fetcher.mime import MIMEDetector

# Scrapers & Parsers
from .scrapers import BaseScraper, ScraperRegistry, GenericScraper
from .scrapers.discovery import ScraperDiscovery
from .scrapers.parsers import HTMLParser, PDFParser, MarkdownParser, TextParser, XMLParser, RSSParser

# Cleaner
from .cleaner import ContentCleaner

# Tokenizer
from .tokenizer import Tokenizer, TextNormalizer

# Indexer
from .indexer import (
    InvertedIndex, PostingEntry,
    DocumentStore, MetadataIndex, LinkGraph,
    Indexer, IndexStats,
)

# Storage
from .storage.sqlite_store import SQLiteStore

# Search
from .search import (
    QueryParser, ParsedQuery, Ranker, SearchEngine,
    SearchResult, SnippetGenerator, BM25Ranker,
    ResultCache, SearchAnalytics, DomainAuthority,
    SearchHighlighter,
)

# Utils
from .utils.benchmark import Benchmark

__all__ = [
    # Models
    "PageDocument",
    # Crawler
    "URLFrontier", "CrawlScheduler", "RobotsChecker", "SitemapDiscovery", "WebCrawler",
    "CrawlPolicy", "CrawlPolicyManager",
    "CrawlManager", "CrawlJob", "JobStatus",
    "SeedManager", "SeedEntry",
    "RevisitPolicyManager", "RevisitSchedule",
    "CrawlHistory", "CrawlRecord",
    "CrawlDashboard", "URLScorer", "URLNormalizer",
    # Fetcher
    "HTTPClient", "Downloader", "RawResponse", "MIMEDetector",
    # Scrapers & Parsers
    "BaseScraper", "ScraperRegistry", "GenericScraper", "ScraperDiscovery",
    "HTMLParser", "PDFParser", "MarkdownParser", "TextParser", "XMLParser", "RSSParser",
    # Cleaner
    "ContentCleaner",
    # Tokenizer
    "Tokenizer", "TextNormalizer",
    # Indexer
    "InvertedIndex", "PostingEntry",
    "DocumentStore", "MetadataIndex", "LinkGraph",
    "Indexer", "IndexStats",
    # Storage
    "SQLiteStore",
    # Search
    "QueryParser", "ParsedQuery", "Ranker", "SearchEngine",
    "SearchResult", "SnippetGenerator", "BM25Ranker",
    "ResultCache", "SearchAnalytics", "DomainAuthority",
    "SearchHighlighter",
    # Utils
    "Benchmark",
]
