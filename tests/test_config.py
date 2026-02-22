"""Tests for the CrawlerConfig loader."""

import pathlib
import tempfile

import pytest
import yaml

from src.config import CrawlerConfig


def _write_config(data: dict) -> pathlib.Path:
    """Write a temporary config YAML and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    yaml.dump(data, tmp)
    tmp.close()
    return pathlib.Path(tmp.name)


def test_loads_valid_config():
    """A well-formed config.yml should produce a correct CrawlerConfig."""
    path = _write_config({
        "start_url": "https://example.com/",
        "rate_limit": 2.5,
        "max_retries": 5,
        "num_fetchers": 8,
    })
    cfg = CrawlerConfig.from_yaml(path)

    assert cfg.start_url == "https://example.com/"
    assert cfg.rate_limit == 2.5
    assert cfg.max_retries == 5
    assert cfg.num_fetchers == 8


def test_num_fetchers_defaults_to_one():
    """If num_fetchers is omitted, it should default to 1."""
    path = _write_config({
        "start_url": "https://example.com/",
        "rate_limit": 1.0,
        "max_retries": 3,
    })
    cfg = CrawlerConfig.from_yaml(path)

    assert cfg.num_fetchers == 1


def test_missing_required_key_raises():
    """Missing a required key (e.g. start_url) should raise a KeyError."""
    path = _write_config({
        "rate_limit": 1.0,
        "max_retries": 3,
    })
    with pytest.raises(KeyError):
        CrawlerConfig.from_yaml(path)


def test_rate_limit_zero():
    """rate_limit=0 should be loaded as 0.0 (no delay)."""
    path = _write_config({
        "start_url": "https://example.com/",
        "rate_limit": 0,
        "max_retries": 3,
    })
    cfg = CrawlerConfig.from_yaml(path)

    assert cfg.rate_limit == 0.0
