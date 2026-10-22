"""
Crawl Dashboard
===============
Exposes crawler statistics for monitoring.
"""

from typing import Dict
from .manager import CrawlManager


class CrawlDashboard:
    """
    Provides a read-only view of crawl statistics.
    """

    def __init__(self, manager: CrawlManager):
        self._manager = manager

    def get_stats(self) -> Dict:
        """Get comprehensive crawl statistics."""
        jobs = self._manager.get_all_jobs()

        pages_crawled = sum(j.urls_crawled for j in jobs)
        pages_indexed = sum(j.urls_indexed for j in jobs)
        failed = sum(j.urls_failed for j in jobs)
        active = [j for j in jobs if j.status.value == "running"]

        return {
            "pages_crawled": pages_crawled,
            "pages_indexed": pages_indexed,
            "queue_size": sum(j.urls_crawled for j in jobs if j.status.value == "pending"),
            "failed_urls": failed,
            "current_domain": active[0].domain if active else None,
            "domains_indexed": len(set(j.domain for j in jobs if j.status.value == "completed")),
            "active_jobs": len(active),
            "total_jobs": len(jobs),
        }

    def format_stats(self) -> str:
        """Format statistics as readable string."""
        stats = self.get_stats()
        lines = [
            "=== Crawl Dashboard ===",
            f"Pages Crawled:    {stats['pages_crawled']}",
            f"Pages Indexed:    {stats['pages_indexed']}",
            f"Queue Size:       {stats['queue_size']}",
            f"Failed URLs:      {stats['failed_urls']}",
            f"Current Domain:   {stats['current_domain'] or 'None'}",
            f"Domains Indexed:  {stats['domains_indexed']}",
            f"Active Jobs:      {stats['active_jobs']}",
            f"Total Jobs:       {stats['total_jobs']}",
            "======================",
        ]
        return "\n".join(lines)
