"""Frontier – manages the URL queue and the 'seen' set.

The frontier wraps an ``asyncio.PriorityQueue`` so that retry items
whose ``scheduled_at`` timestamp hasn't arrived yet are deferred
rather than blocking the event loop.
"""

from __future__ import annotations

import asyncio
import time
from typing import Set

from src.models import FrontierItem


class Frontier:
    """Thread-safe (async) frontier backed by a priority queue."""

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[FrontierItem] = asyncio.PriorityQueue()
        self._seen: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def push(self, item: FrontierItem) -> None:
        """Add *item* to the frontier if this URL hasn't been seen yet.

        For retries the URL is already in ``_seen``, so we skip the
        dedup check and push unconditionally.
        """
        if item.retry_count == 0:
            if item.url in self._seen:
                return
            self._seen.add(item.url)
        await self._queue.put(item)

    async def pop(self) -> FrontierItem:
        """Return the next item.

        If the item's ``scheduled_at`` is in the future, sleep until
        that time so we respect the backoff schedule without spinning.
        """
        item = await self._queue.get()
        delay = item.scheduled_at - time.time()
        if delay > 0:
            await asyncio.sleep(delay)
        return item

    def task_done(self) -> None:
        """Mark the most recently popped item as done."""
        self._queue.task_done()

    async def join(self) -> None:
        """Block until all items have been processed."""
        await self._queue.join()

    @property
    def seen(self) -> Set[str]:
        """Return the set of URLs that have already been queued."""
        return self._seen

    @property
    def empty(self) -> bool:
        return self._queue.empty()

    @property
    def qsize(self) -> int:
        """Return the approximate number of items in the frontier queue."""
        return self._queue.qsize()
