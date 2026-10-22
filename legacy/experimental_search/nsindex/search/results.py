"""
Rich Search Results
===================
Standardized search result objects with rich metadata.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class SearchResult:
    """
    Rich search result returned by the search engine.
    Designed for extensibility — additional metadata can be added later.
    """

    # ── Core Fields ───────────────────────────────────────────────────────
    title: str = ""
    url: str = ""
    domain: str = ""
    snippet: str = ""

    # ── Metadata ──────────────────────────────────────────────────────────
    language: str = ""
    content_length: int = 0
    last_indexed: float = 0.0

    # ── Ranking ───────────────────────────────────────────────────────────
    score: float = 0.0
    rank: int = 0

    # ── Extended Metadata (future-proof) ──────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary for API/UI consumption."""
        return {
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "snippet": self.snippet,
            "language": self.language,
            "content_length": self.content_length,
            "last_indexed": self.last_indexed,
            "score": self.score,
            "rank": self.rank,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SearchResult":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
