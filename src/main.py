"""Main orchestrator for the web crawler.

1. Config is loaded from config.yml.
2. robots.txt is fetched and parsed.
3. Frontier is initialized with the starting URL.
4. Fetcher and Parser workers are spawned.
5. Crawl completes when the frontier is empty and the timeout is reached.
6. Results are saved to results.json.
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

logger = logging.getLogger(__name__)


async def crawl() -> dict:
    """Run the full crawl pipeline and return the results dictionary."""

    # 1. Load configuration
    config = CrawlerConfig.from_yaml()

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    logger.info("Starting crawl from %s", config.start_url)

    allowed_domain = urlparse(config.start_url).netloc

    # 2. Fetch & parse robots.txt
    robot_rules = RobotRules()
    await robot_rules.fetch(config.start_url)

    # 3. Initialise queues & workers
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()

    fetchers = [
        Fetcher(config, frontier, parse_queue, robot_rules)
        for _ in range(config.num_fetchers)
    ]
    parser = Parser(allowed_domain, frontier, parse_queue)

    logger.info("Spawning %d fetcher worker(s)", config.num_fetchers)

    # Add the frontier with the starting URL.
    await frontier.push(FrontierItem.new(config.start_url))

    # 4. Run workers concurrently
    await asyncio.gather(*[f.run() for f in fetchers], parser.run())

    # 5. Format results
    all_dropped: list[str] = []
    for f in fetchers:
        all_dropped.extend(f.dropped)

    results: dict = {**parser.urls_found, "Dropped sites": all_dropped}

    # 6. Save results to results.json
    output_path = pathlib.Path(__file__).resolve().parent.parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", output_path)

    return results


def main() -> None:
    asyncio.run(crawl())


if __name__ == "__main__":
    main()
