"""
Crawl Manager
=============
Manages crawl jobs, progress, and statistics.
"""

import time
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CrawlJob:
    """Represents a single crawl job for a domain."""
    domain: str
    status: JobStatus = JobStatus.PENDING
    urls_crawled: int = 0
    urls_indexed: int = 0
    urls_failed: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0
    error: Optional[str] = None


class CrawlManager:
    """
    Manages multiple crawl jobs across domains.
    """

    def __init__(self):
        self._jobs: Dict[str, CrawlJob] = {}
        self._lock = threading.Lock()

    def create_job(self, domain: str) -> CrawlJob:
        """Create a new crawl job for a domain."""
        with self._lock:
            job = CrawlJob(domain=domain)
            self._jobs[domain] = job
            return job

    def get_job(self, domain: str) -> Optional[CrawlJob]:
        return self._jobs.get(domain)

    def start_job(self, domain: str):
        job = self._jobs.get(domain)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()

    def complete_job(self, domain: str):
        job = self._jobs.get(domain)
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()

    def fail_job(self, domain: str, error: str):
        job = self._jobs.get(domain)
        if job:
            job.status = JobStatus.FAILED
            job.error = error

    def pause_job(self, domain: str):
        job = self._jobs.get(domain)
        if job:
            job.status = JobStatus.PAUSED

    def resume_job(self, domain: str):
        job = self._jobs.get(domain)
        if job:
            job.status = JobStatus.RUNNING

    def get_active_jobs(self) -> List[CrawlJob]:
        return [j for j in self._jobs.values() if j.status == JobStatus.RUNNING]

    def get_all_jobs(self) -> List[CrawlJob]:
        return list(self._jobs.values())

    def get_statistics(self) -> Dict:
        total_crawled = sum(j.urls_crawled for j in self._jobs.values())
        total_indexed = sum(j.urls_indexed for j in self._jobs.values())
        total_failed = sum(j.urls_failed for j in self._jobs.values())
        return {
            "total_jobs": len(self._jobs),
            "active_jobs": len(self.get_active_jobs()),
            "total_urls_crawled": total_crawled,
            "total_urls_indexed": total_indexed,
            "total_urls_failed": total_failed,
        }
