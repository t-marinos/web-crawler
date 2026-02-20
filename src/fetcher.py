"""Fetcher worker – pulls URLs from the frontier and fetches HTML.

Responsibilities:
* Respect rate-limiting (configurable delay between requests).
* Respect robots.txt disallow rules.
* Handle HTTP errors:
  - 404 → drop the URL and record it.
  - Other failures → schedule a retry with exponential backoff, or
    drop after ``max_retries`` attempts.
* Push successfully fetched pages onto the parsing queue.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

import aiohttp

from src.config import CrawlerConfig
from src.frontier import Frontier
from src.models import FrontierItem, ParseItem
from src.utils.robot import RobotRules

logger = logging.getLogger(__name__)


class Fetcher:
    """Asynchronous fetcher worker."""

    def __init__(
        self,
        config: CrawlerConfig,
        frontier: Frontier,
        parse_queue: asyncio.Queue[ParseItem],
        robot_rules: RobotRules,
    ) -> None:
        self._config = config
        self._frontier = frontier
        self._parse_queue = parse_queue
        self._robot_rules = robot_rules

        # Track dropped URLs and their reasons.
        self.dropped: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run the fetcher loop until the frontier signals completion."""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    item = await asyncio.wait_for(self._frontier.pop(), timeout=10)
                except asyncio.TimeoutError:
                    # No new items for 5 s — assume crawl is finished.
                    break

                await self._process(session, item)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process(self, session: aiohttp.ClientSession, item: FrontierItem) -> None:
        url = item.url

        logger.info(
            "Fetcher | frontier_queue=%d  parse_queue=%d  | processing %s",
            self._frontier.qsize,
            self._parse_queue.qsize(),
            url,
        )

        # Politeness: respect robots.txt.
        if not self._robot_rules.is_allowed(url):
            logger.info("Blocked by robots.txt: %s", url)
            self._frontier.task_done()
            return

        # Rate-limit: honour the configured delay (or robots.txt crawl-delay).
        delay = self._effective_delay()
        await asyncio.sleep(delay)

        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True
            ) as resp:
                if resp.status == 404:
                    logger.warning("404 – dropping %s", url)
                    self.dropped.append(url)
                    self._frontier.task_done()
                    return

                if resp.status >= 400:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=f"HTTP {resp.status}",
                    )

                html = await resp.text()

        except Exception as exc:
            await self._handle_failure(item, exc)
            return

        # Success – push to the parsing queue.
        await self._parse_queue.put(ParseItem(url=url, html=html))
        self._frontier.task_done()

    async def _handle_failure(self, item: FrontierItem, exc: Exception) -> None:
        """Decide whether to retry or drop this URL."""
        next_retry = item.retry_count + 1

        if next_retry >= self._config.max_retries:
            logger.error(
                "Dropping %s after %d retries – last error: %s",
                item.url,
                next_retry,
                exc,
            )
            self.dropped.append(item.url)
            self._frontier.task_done()
            return

        # Exponential backoff: 2^retry seconds (2 s, 4 s, 8 s, …).
        backoff = 2 ** next_retry
        scheduled_at = time.time() + backoff
        logger.warning(
            "Retrying %s (attempt %d) in %ds – error: %s",
            item.url,
            next_retry,
            backoff,
            exc,
        )

        retry_item = FrontierItem(
            scheduled_at=scheduled_at,
            url=item.url,
            retry_count=next_retry,
        )
        await self._frontier.push(retry_item)
        self._frontier.task_done()

    def _effective_delay(self) -> float:
        """Return the delay to apply between requests.

        If ``rate_limit`` is 0, no artificial delay is applied (unless
        robots.txt specifies a ``crawl-delay``).
        """
        robots_delay = self._robot_rules.crawl_delay()
        config_delay = self._config.rate_limit

        if robots_delay is not None:
            return max(config_delay, robots_delay)
        return config_delay
