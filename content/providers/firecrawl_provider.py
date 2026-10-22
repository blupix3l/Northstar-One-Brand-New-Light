"""
Firecrawl Content Provider
==========================
Content acquisition using Firecrawl's scrape API.
First implementation of the ContentProvider interface.
"""

import os
from ..content_provider import ContentProvider
from ..page_profile import PageProfile


class FirecrawlContentProvider(ContentProvider):
    """Enriches pages using Firecrawl's scrape API."""

    name = "firecrawl"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("FIRECRAWL_API_KEY", "")
        self._app = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_app(self):
        if self._app is None and self.api_key:
            from firecrawl import FirecrawlApp
            self._app = FirecrawlApp(api_key=self.api_key, timeout=20)
        return self._app

    def enrich(self, profile: PageProfile) -> PageProfile:
        app = self._get_app()
        if not app:
            return profile

        try:
            result = app.scrape_url(profile.url, formats=["markdown"])

            if not result:
                return profile

            # ── Metadata ──────────────────────────────────────────────────
            meta = getattr(result, 'metadata', None)
            if meta:
                profile.title = getattr(meta, 'title', None) or profile.title
                profile.description = getattr(meta, 'description', None) or profile.description
                profile.language = getattr(meta, 'language', None)
                profile.favicon = getattr(meta, 'favicon', None) or profile.favicon

                profile.page_metadata = {
                    "source_url": getattr(meta, 'source_url', ''),
                    "status_code": getattr(meta, 'status_code', 0),
                    "proxy_used": getattr(meta, 'proxy_used', ''),
                    "og_title": getattr(meta, 'og_title', None),
                    "og_description": getattr(meta, 'og_description', None),
                    "og_image": getattr(meta, 'og_image', None),
                    "keywords": getattr(meta, 'keywords', None),
                }

            # ── Markdown Content ──────────────────────────────────────────
            profile.markdown_content = getattr(result, 'markdown', None) or ""
            profile.provider = self.name

            # ── Extract Headings ──────────────────────────────────────────
            if profile.markdown_content:
                profile.extracted_headings = [
                    line.strip().lstrip("#").strip()
                    for line in profile.markdown_content.split("\n")
                    if line.strip().startswith("#")
                ][:20]

            # ── Images ────────────────────────────────────────────────────
            images = getattr(result, 'images', None) or []
            profile.page_images = [img for img in images if isinstance(img, str)][:20]

            # ── Hero Image ────────────────────────────────────────────────
            profile.hero_image = getattr(result, 'screenshot', None)
            if not profile.hero_image and meta:
                profile.hero_image = getattr(meta, 'og_image', None)

        except Exception as e:
            print(f"[ENRICH] Firecrawl error for {profile.url}: {e}")

        return profile
