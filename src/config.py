"""Configuration loader for the web crawler.

Reads settings from config.yml and exposes them as a typed dataclass.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import yaml

CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "config.yml"


@dataclass(frozen=True)
class CrawlerConfig:
    """Immutable configuration for the crawler."""

    start_url: str
    rate_limit: float
    max_retries: int
    num_fetchers: int
    max_concurrent: int
    log_level: str

    @classmethod
    def from_yaml(cls, path: pathlib.Path = CONFIG_PATH) -> CrawlerConfig:
        """Load configuration from config.yml."""
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh)

        num_fetchers = int(raw.get("num_fetchers", 1))
        return cls(
            start_url=raw["start_url"],
            rate_limit=float(raw.get("rate_limit", 0)),
            max_retries=int(raw["max_retries"]),
            num_fetchers=num_fetchers,
            max_concurrent=int(raw.get("max_concurrent", num_fetchers)),
            log_level=raw.get("log_level", "INFO").upper(),
        )
