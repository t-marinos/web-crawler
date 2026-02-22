"""Tests for the Fetcher worker"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import CrawlerConfig
from src.fetcher import Fetcher
from src.frontier import Frontier
from src.models import FrontierItem, ParseItem
from src.utils.robot import RobotRules


def _make_fetcher() -> tuple[Fetcher, Frontier, asyncio.Queue]:
    """Helper to create a Fetcher with a valid config."""
    config = CrawlerConfig(start_url="https://example.com", rate_limit=0.0, max_retries=3, num_fetchers=1, log_level="INFO")
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()
    robot_rules = RobotRules()
    robot_rules._loaded = True
    robot_rules._parser.allow_all = True
    fetcher = Fetcher(config, frontier, parse_queue, robot_rules)
    return fetcher, frontier, parse_queue


@pytest.mark.asyncio
async def test_404_is_dropped():
    """A 404 response should drop the URL without retrying."""
    fetcher, frontier, parse_queue = _make_fetcher()

    item = FrontierItem.new("https://example.com/missing")
    await frontier.push(item)

    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    popped = await frontier.pop()
    await fetcher._process(mock_session, popped)

    assert "https://example.com/missing" in fetcher.dropped
    assert parse_queue.empty()


@pytest.mark.asyncio
async def test_successful_fetch_pushes_to_parse_queue():
    """A 200 response should put the result on the parse queue."""
    fetcher, frontier, parse_queue = _make_fetcher()

    item = FrontierItem.new("https://example.com/page")
    await frontier.push(item)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="<html></html>")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    popped = await frontier.pop()
    await fetcher._process(mock_session, popped)

    assert not parse_queue.empty()
    result = await parse_queue.get()
    assert result.url == "https://example.com/page"
    assert result.html == "<html></html>"


@pytest.mark.asyncio
async def test_server_error_retries():
    """A 500 error should schedule a retry with exponential backoff."""
    fetcher, frontier, parse_queue = _make_fetcher()

    item = FrontierItem.new("https://example.com/error")
    await frontier.push(item)

    mock_resp = AsyncMock()
    mock_resp.status = 500
    mock_resp.request_info = MagicMock()
    mock_resp.history = ()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    popped = await frontier.pop()
    await fetcher._process(mock_session, popped)

    # URL should NOT be dropped yet (only 1st attempt)
    assert "https://example.com/error" not in fetcher.dropped

    # It should be re-queued on the frontier with retry_count=1
    assert not frontier.empty
    retry_item = await frontier.pop()
    assert retry_item.url == "https://example.com/error"
    assert retry_item.retry_count == 1
    assert retry_item.scheduled_at > time.time() - 1  # should be in the near future


@pytest.mark.asyncio
async def test_max_retries_drops():
    """After max_retries, the URL should be dropped permanently."""
    fetcher, frontier, parse_queue = _make_fetcher()

    # Simulate a URL that has already been retried max_retries
    item = FrontierItem(
        scheduled_at=time.time(),
        url="https://example.com/flaky",
        retry_count=2,  # next failure = attempt 3 = max_retries so we drop it
    )
    await frontier.push(item)

    exc = Exception("connection timeout")
    popped = await frontier.pop()
    await fetcher._handle_failure(popped, exc)

    assert "https://example.com/flaky" in fetcher.dropped
    assert frontier.empty
