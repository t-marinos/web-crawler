"""Main orchestrator for the web crawler.

Wiring:
  config.yml → CrawlerConfig
  robots.txt → RobotRules
  Frontier  <──  Fetcher  ──>  ParseQueue  <──  Parser  ──>  Frontier
                                                          (new URLs)

Usage:
    python -m src.main
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from urllib.parse import urlparse

from src.config import CrawlerConfig
from src.fetcher import Fetcher
from src.frontier import Frontier
from src.models import FrontierItem, ParseItem
from src.parser import Parser
from src.utils.robot import RobotRules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


async def crawl() -> dict:
    """Run the full crawl pipeline and return the results dictionary."""

    # ── 1. Load configuration ────────────────────────────────────────
    config = CrawlerConfig.from_yaml()
    logger.info("Starting crawl from %s", config.start_url)

    allowed_domain = urlparse(config.start_url).netloc

    # ── 2. Fetch & parse robots.txt ──────────────────────────────────
    robot_rules = RobotRules()
    await robot_rules.fetch(config.start_url)

    # ── 3. Initialise queues & workers ───────────────────────────────
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()

    fetchers = [
        Fetcher(config, frontier, parse_queue, robot_rules)
        for _ in range(config.num_fetchers)
    ]
    parser = Parser(allowed_domain, frontier, parse_queue)

    logger.info("Spawning %d fetcher worker(s)", config.num_fetchers)

    # Seed the frontier with the starting URL.
    await frontier.push(FrontierItem.new(config.start_url))

    # ── 4. Run workers concurrently ──────────────────────────────────
    await asyncio.gather(*[f.run() for f in fetchers], parser.run())

    # ── 5. Build results ─────────────────────────────────────────────
    all_dropped: list[str] = []
    for f in fetchers:
        all_dropped.extend(f.dropped)

    results: dict = {**parser.urls_found, "Dropped sites": all_dropped}

    print(f"\n{'='*60}")
    print("CRAWL COMPLETE")
    print(f"{'='*60}")

    output_path = pathlib.Path(__file__).resolve().parent.parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_path}")

    return results


def main() -> None:
    asyncio.run(crawl())


if __name__ == "__main__":
    main()
