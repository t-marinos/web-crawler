"""robots.txt helper.

Fetches and parses the robots.txt file for the target domain once at
startup and exposes convenience methods for checking crawl permissions
and retrieving the crawl-delay directive.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import aiohttp

logger = logging.getLogger(__name__)

USER_AGENT = "MonzoCrawler/1.0"


class RobotRules:
    """Uses `urllib.robotparser.RobotFileParser` to check crawl permissions."""

    def __init__(self) -> None:
        self._parser = RobotFileParser()
        self._loaded = False

    async def fetch(self, base_url: str) -> None:
        """Download and parse robots.txt for *base_url*."""
        robots_url = urljoin(base_url, "/robots.txt")
        headers = {"User-Agent": USER_AGENT}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        self._parser.parse(text.splitlines())
                        logger.info("Loaded robots.txt from %s", robots_url)
                    else:
                        # If robots.txt is missing or returns non-200,
                        # assume everything is allowed.
                        logger.warning(
                            "robots.txt returned status %s so we are allowing all paths",
                            resp.status,
                        )
                        error_text = await resp.text()
                        logger.warning("robots.txt: %s", error_text)
                        self._parser.allow_all = True
        except Exception:
            logger.warning("Failed to fetch robots.txt so we are allowing all paths", exc_info=True)
            self._parser.allow_all = True

        self._loaded = True

    def is_allowed(self, url: str) -> bool:
        """Return *True* if *url* may be crawled according to robots.txt."""
        if not self._loaded:
            return True
        return self._parser.can_fetch(USER_AGENT, url)

    def crawl_delay(self) -> float | None:
        """Return the crawl-delay for our user-agent, or *None*."""
        if not self._loaded:
            return None
        delay = self._parser.crawl_delay(USER_AGENT)
        return float(delay) if delay is not None else None
