"""
Revisit Policies
================
Configurable schedules for revisiting pages.
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class RevisitSchedule:
    """Schedule for revisiting a page or domain."""
    interval_seconds: float = 86400  # Default: 1 day
    last_visited: float = 0.0
    next_scheduled: float = 0.0

    def is_due(self) -> bool:
        """Check if it's time to revisit."""
        return time.time() >= self.next_scheduled

    def record_visit(self):
        """Record a visit and schedule next."""
        self.last_visited = time.time()
        self.next_scheduled = self.last_visited + self.interval_seconds


class RevisitPolicyManager:
    """
    Manages revisit schedules for domains and URLs.
    """

    PRESET_POLICIES = {
        "news": 3600,        # 1 hour
        "blog": 86400,       # 1 day
        "docs": 604800,      # 7 days
        "wikipedia": 2592000, # 30 days
        "static": 2592000,   # 30 days
        "default": 86400,    # 1 day
    }

    def __init__(self):
        self._schedules: Dict[str, RevisitSchedule] = {}
        self._domain_defaults: Dict[str, str] = {}

    def set_domain_policy(self, domain: str, policy_name: str):
        """Set a named policy for a domain."""
        interval = self.PRESET_POLICIES.get(policy_name, 86400)
        self._domain_defaults[domain] = policy_name
        if domain in self._schedules:
            self._schedules[domain].interval_seconds = interval

    def get_schedule(self, url: str, domain: str = "") -> RevisitSchedule:
        """Get or create a revisit schedule for a URL."""
        if url in self._schedules:
            return self._schedules[url]

        # Use domain default if available
        policy_name = self._domain_defaults.get(domain, "default")
        interval = self.PRESET_POLICIES.get(policy_name, 86400)

        schedule = RevisitSchedule(interval_seconds=interval)
        self._schedules[url] = schedule
        return schedule

    def is_due(self, url: str) -> bool:
        """Check if a URL is due for revisiting."""
        schedule = self._schedules.get(url)
        if not schedule:
            return True  # Never visited = due
        return schedule.is_due()

    def record_visit(self, url: str):
        """Record a visit to a URL."""
        if url in self._schedules:
            self._schedules[url].record_visit()

    def get_next_revisit(self) -> Optional[str]:
        """Get the URL with the earliest next scheduled visit."""
        due = [(url, s.next_scheduled) for url, s in self._schedules.items() if s.is_due()]
        if due:
            due.sort(key=lambda x: x[1])
            return due[0][0]
        return None
