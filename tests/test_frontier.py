"""Tests for the Frontier class."""

import asyncio
import time

import pytest

from src.frontier import Frontier
from src.models import FrontierItem


@pytest.mark.asyncio
async def test_push_deduplicates():
    """Pushing the same URL twice should only enqueue it once."""
    frontier = Frontier()
    item1 = FrontierItem.new("https://example.com/a")
    item2 = FrontierItem.new("https://example.com/a")

    await frontier.push(item1)
    await frontier.push(item2)

    assert len(frontier.seen) == 1

    popped = await frontier.pop()
    assert popped.url == "https://example.com/a"
    assert frontier.empty


@pytest.mark.asyncio
async def test_push_retry_bypasses_dedup():
    """A retry item (retry_count > 0) should always be enqueued."""
    frontier = Frontier()
    original = FrontierItem.new("https://example.com/a")
    await frontier.push(original)
    await frontier.pop()

    retry = FrontierItem(
        scheduled_at=time.time(), url="https://example.com/a", retry_count=1
    )
    await frontier.push(retry)
    assert not frontier.empty


@pytest.mark.asyncio
async def test_priority_ordering():
    """Items should be popped in order of scheduled_at (earliest first)."""
    frontier = Frontier()
    now = time.time()

    late = FrontierItem(scheduled_at=now + 100, url="https://example.com/late", retry_count=0)
    early = FrontierItem(scheduled_at=now - 1, url="https://example.com/early", retry_count=0)

    await frontier.push(late)
    await frontier.push(early)

    first = await frontier.pop()
    assert first.url == "https://example.com/early"
