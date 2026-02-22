"""Parser worker that extracts links from fetched HTML.

Responsibilities of the parser worker:
* Pull items from the parsing queue.
* Extract all ``<a href="…">`` links using BeautifulSoup.
* Normalise and filter URLs to the same subdomain.
* Logs the visited URL and its discovered links.
* Push unseen same domain links onto the frontier.
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

        # url is mapped to a list of all links found on that page (including external).
        self.urls_found: Dict[str, List[str]] = {}

    async def run(self) -> None:
        """Consume items from the parsing queue until idle."""
        while True:
            try:
                item = await asyncio.wait_for(self._parse_queue.get(), 10)
            except asyncio.TimeoutError:
                break

            await self.process(item)
            self._parse_queue.task_done()

    async def process(self, item: ParseItem) -> None:
        logger.info(
            "Parser  | frontier_queue=%d  parse_queue=%d  | parsing %s",
            self._frontier.qsize,
            self._parse_queue.qsize(),
            item.url,
        )

        links = self.extract_links(item.url, item.html)
        self.urls_found[item.url] = links

        # Log output.
        links_str = "\n".join(f"   {link}" for link in links)
        logger.info(
            "Visited: %s\nLinks found (%d):\n%s",
            item.url, len(links), links_str,
        )

        # Push same domain links to the frontier.
        for link in links:
            if self.is_same_domain(link):
                await self._frontier.push(FrontierItem.new(link))

    def extract_links(self, base_url: str, html: str) -> List[str]:
        """Return a deduplicated list of absolute URLs found in *html*."""
        soup = BeautifulSoup(html, "html.parser")
        seen: Set[str] = set()
        links: List[str] = []

        for anchor in soup.find_all("a", href=True):
            raw_href: str = anchor["href"]
            absolute = urljoin(base_url, raw_href)

            # Strip fragments.
            parsed = urlparse(absolute)
            clean = parsed._replace(fragment="").geturl()

            if clean not in seen:
                seen.add(clean)
                links.append(clean)

        return links

    def is_same_domain(self, url: str) -> bool:
        """Return *True* if *url* belongs to the allowed subdomain."""
        parsed = urlparse(url)
        return parsed.netloc == self._allowed_domain
