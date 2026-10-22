"""
Page Document Model
===================
Universal contract between scrapers and the rest of NSIndex.
Every scraper MUST return this object.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class PageDocument:
    """
    Universal page document returned by all scrapers.
    This is the contract — no indexing logic belongs here.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    url: str = ""
    title: str = ""
    description: str = ""
    domain: str = ""

    # ── Content ───────────────────────────────────────────────────────────────
    text: str = ""
    headings: List[str] = field(default_factory=list)

    # ── Links & Media ─────────────────────────────────────────────────────────
    links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)

    # ── Metadata ──────────────────────────────────────────────────────────────
    language: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    # ── Indexing Fields ───────────────────────────────────────────────────────
    doc_id: int = 0                     # Unique integer ID assigned by indexer
    content_hash: str = ""              # SHA-256 of cleaned text
    indexed_at: float = 0.0             # When this document was indexed

    # ── Timestamps ────────────────────────────────────────────────────────────
    fetched_at: float = 0.0
    scraped_at: float = 0.0

    def __post_init__(self):
        if self.url and not self.domain:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            self.domain = parsed.netloc

    def is_valid(self) -> bool:
        """Check if document has meaningful content."""
        return bool(self.url and (self.title or self.text))

    def word_count(self) -> int:
        return len(self.text.split()) if self.text else 0

    def compute_content_hash(self) -> str:
        """Generate SHA-256 hash of the cleaned text content."""
        content = (self.title + " " + self.text).strip().lower()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "doc_id": self.doc_id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "domain": self.domain,
            "text": self.text,
            "headings": self.headings,
            "links": self.links,
            "images": self.images,
            "language": self.language,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
            "indexed_at": self.indexed_at,
            "fetched_at": self.fetched_at,
            "scraped_at": self.scraped_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PageDocument":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
