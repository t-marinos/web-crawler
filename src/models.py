"""Data models used across the crawler pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(order=True)
class FrontierItem:
    """An item on the Frontier queue.

    Ordering is by ``scheduled_at`` so the priority queue processes URLs
    whose retry time has arrived first.

    Attributes:
        scheduled_at: Earliest epoch time this URL should be fetched.
        url:          The URL to crawl (excluded from ordering).
        retry_count:  How many times we have already retried this URL.
    """

    scheduled_at: float
    url: str = field(compare=False)
    retry_count: int = field(default=0, compare=False)

    @classmethod
    def new(cls, url: str) -> FrontierItem:
        """Create a brand-new item scheduled for immediate processing."""
        return cls(scheduled_at=time.time(), url=url, retry_count=0)


@dataclass
class ParseItem:
    """An item on the Parsing queue.

    Attributes:
        url:  The URL that was fetched.
        html: The raw HTML body returned by the server.
    """

    url: str
    html: str
