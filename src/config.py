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
    rate_limit: float  # minimum seconds between requests
    max_retries: int
    num_fetchers: int

    @classmethod
    def from_yaml(cls, path: pathlib.Path = CONFIG_PATH) -> CrawlerConfig:
        """Load configuration from a YAML file."""
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh)

        return cls(
            start_url=raw["start_url"],
            rate_limit=float(raw["rate_limit"]),
            max_retries=int(raw["max_retries"]),
            num_fetchers=int(raw.get("num_fetchers", 1)),
        )
