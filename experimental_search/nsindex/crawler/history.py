"""
Crawl History
=============
Tracks crawl history for incremental crawling.
"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class CrawlRecord:
    """Record of a single crawl attempt."""
    url: str
    timestamp: float = 0.0
    status_code: int = 0
    fetch_duration_ms: float = 0.0
    content_hash: str = ""
    change_detected: bool = False
    error: Optional[str] = None


class CrawlHistory:
    """
    Maintains history of crawl attempts.
    Useful for incremental crawling and change detection.
    """

    def __init__(self, max_per_domain: int = 1000):
        self._records: Dict[str, List[CrawlRecord]] = {}
        self._max_per_domain = max_per_domain

    def record(self, url: str, status_code: int, fetch_duration_ms: float,
               content_hash: str = "", change_detected: bool = False,
               error: str = None):
        """Record a crawl attempt."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        record = CrawlRecord(
            url=url,
            timestamp=time.time(),
            status_code=status_code,
            fetch_duration_ms=fetch_duration_ms,
            content_hash=content_hash,
            change_detected=change_detected,
            error=error,
        )

        if domain not in self._records:
            self._records[domain] = []

        self._records[domain].append(record)

        # Trim if too many records
        if len(self._records[domain]) > self._max_per_domain:
            self._records[domain] = self._records[domain][-self._max_per_domain:]

    def get_last_crawl(self, url: str) -> Optional[CrawlRecord]:
        """Get the last crawl record for a URL."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        records = self._records.get(domain, [])
        for record in reversed(records):
            if record.url == url:
                return record
        return None

    def has_changed(self, url: str, current_hash: str) -> bool:
        """Check if content has changed since last crawl."""
        last = self.get_last_crawl(url)
        if not last:
            return True  # Never crawled = changed
        return last.content_hash != current_hash

    def get_domain_stats(self, domain: str) -> Dict:
        """Get statistics for a domain."""
        records = self._records.get(domain, [])
        if not records:
            return {}

        successful = [r for r in records if 200 <= r.status_code < 400]
        failed = [r for r in records if r.error or r.status_code >= 400]
        changed = [r for r in records if r.change_detected]

        avg_duration = sum(r.fetch_duration_ms for r in successful) / len(successful) if successful else 0

        return {
            "total_crawls": len(records),
            "successful": len(successful),
            "failed": len(failed),
            "changed": len(changed),
            "avg_fetch_ms": round(avg_duration, 1),
        }

    def get_all_stats(self) -> Dict:
        """Get overall statistics."""
        total = sum(len(records) for records in self._records.values())
        all_records = [r for records in self._records.values() for r in records]
        successful = [r for r in all_records if 200 <= r.status_code < 400]
        changed = [r for r in all_records if r.change_detected]

        return {
            "total_crawls": total,
            "domains": len(self._records),
            "successful": len(successful),
            "changed": len(changed),
        }
