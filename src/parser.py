"""Parser worker – extracts links from fetched HTML.

Responsibilities:
* Pull items from the parsing queue.
* Extract all ``<a href="…">`` links using BeautifulSoup.
* Normalise and filter URLs to the same subdomain.
* Print the visited URL and its discovered links.
* Push unseen same-domain links onto the frontier.
* Populate the ``urls_found`` results dictionary.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.frontier import Frontier
from src.models import FrontierItem, ParseItem

logger = logging.getLogger(__name__)


class Parser:
    """Asynchronous parsing worker."""

    def __init__(
        self,
        allowed_domain: str,
        frontier: Frontier,
        parse_queue: asyncio.Queue[ParseItem],
    ) -> None:
        self._allowed_domain = allowed_domain
        self._frontier = frontier
        self._parse_queue = parse_queue

        # url → list of all links found on that page (including external).
        self.urls_found: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Consume items from the parsing queue until idle."""
        while True:
            try:
                item = await asyncio.wait_for(self._parse_queue.get(), 10)
            except asyncio.TimeoutError:
                break

            await self._process(item)
            self._parse_queue.task_done()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process(self, item: ParseItem) -> None:
        logger.info(
            "Parser  | frontier_queue=%d  parse_queue=%d  | parsing %s",
            self._frontier.qsize,
            self._parse_queue.qsize(),
            item.url,
        )

        links = self._extract_links(item.url, item.html)
        self.urls_found[item.url] = links

        # Pretty-print output.
        print(f"\n{'='*60}")
        print(f"Visited: {item.url}")
        print(f"Links found ({len(links)}):")
        for link in links:
            print(f"  → {link}")

        # Push same-domain links to the frontier.
        for link in links:
            if self._is_same_domain(link):
                await self._frontier.push(FrontierItem.new(link))

    def _extract_links(self, base_url: str, html: str) -> List[str]:
        """Return a deduplicated list of absolute URLs found in *html*."""
        soup = BeautifulSoup(html, "html.parser")
        seen: Set[str] = set()
        links: List[str] = []

        for anchor in soup.find_all("a", href=True):
            raw_href: str = anchor["href"]
            absolute = urljoin(base_url, raw_href)

            # Skip non-HTTP schemes (mailto:, tel:, javascript:, etc.)
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue

            # Strip fragments.
            clean = parsed._replace(fragment="").geturl()

            if clean not in seen:
                seen.add(clean)
                links.append(clean)

        return links

    def _is_same_domain(self, url: str) -> bool:
        """Return *True* if *url* belongs to the allowed subdomain."""
        parsed = urlparse(url)
        return parsed.netloc == self._allowed_domain
