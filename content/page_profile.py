"""
Page Profile
============
Dataclass containing enriched information about a webpage.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class PageProfile:
    """
    Enriched information about a single webpage.
    All fields optional — populated incrementally by enrichment providers.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    url: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    favicon: Optional[str] = None
    language: Optional[str] = None

    # ── Content ───────────────────────────────────────────────────────────────
    markdown_content: str = ""
    extracted_headings: List[str] = field(default_factory=list)

    # ── Media ─────────────────────────────────────────────────────────────────
    hero_image: Optional[str] = None
    page_images: List[str] = field(default_factory=list)

    # ── Metadata ──────────────────────────────────────────────────────────────
    page_metadata: dict = field(default_factory=dict)

    # ── Enrichment Source ─────────────────────────────────────────────────────
    provider: str = ""
    last_updated: float = 0.0

    def __post_init__(self):
        if self.url and not self.domain:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            self.domain = parsed.netloc

    def is_valid(self) -> bool:
        """Check if profile has meaningful content."""
        return bool(self.url and (self.title or self.description or self.markdown_content))

    def to_dict(self) -> dict:
        """Serialize to dictionary for caching."""
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "description": self.description,
            "favicon": self.favicon,
            "language": self.language,
            "markdown_content": self.markdown_content,
            "extracted_headings": self.extracted_headings,
            "hero_image": self.hero_image,
            "page_images": self.page_images,
            "page_metadata": self.page_metadata,
            "provider": self.provider,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PageProfile":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
