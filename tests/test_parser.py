"""Tests for the Parser class"""

import asyncio

import pytest

from src.frontier import Frontier
from src.models import ParseItem
from src.parser import Parser

ALLOWED_DOMAIN = "crawlme.monzo.com"

SAMPLE_HTML = """
<html>
<body>
    <a href="/about">About</a>
    <a href="https://crawlme.monzo.com/contact">Contact</a>
    <a href="https://facebook.com/monzo">Facebook</a>
    <a href="https://monzo.com">Monzo</a>
    <a href="https://community.monzo.com">Community</a>
    <a href="https://crawlme.monzo.com/faq#section1">FAQ</a>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_extract_links():
    """Parser should extract and normalise all href links."""
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()
    parser = Parser(ALLOWED_DOMAIN, frontier, parse_queue)

    links = parser.extract_links("https://crawlme.monzo.com/", SAMPLE_HTML)

    assert "https://crawlme.monzo.com/about" in links
    assert "https://crawlme.monzo.com/contact" in links
    assert "https://facebook.com/monzo" in links
    assert "https://monzo.com" in links
    assert "https://community.monzo.com" in links
    # Fragment should be stripped, yielding /faq without #section1.
    assert "https://crawlme.monzo.com/faq" in links


@pytest.mark.asyncio
async def test_same_domain_filter():
    """Only crawlme.monzo.com links should pass the domain filter."""
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()
    parser = Parser(ALLOWED_DOMAIN, frontier, parse_queue)

    assert parser.is_same_domain("https://crawlme.monzo.com/about") is True
    assert parser.is_same_domain("https://crawlme.monzo.com/contact") is True
    assert parser.is_same_domain("https://facebook.com/monzo") is False
    assert parser.is_same_domain("https://monzo.com") is False
    assert parser.is_same_domain("https://community.monzo.com") is False


@pytest.mark.asyncio
async def test_parser_pushes_only_same_domain_links():
    """After processing HTML, only same-domain links should appear on the frontier."""
    frontier = Frontier()
    parse_queue: asyncio.Queue[ParseItem] = asyncio.Queue()
    parser = Parser(ALLOWED_DOMAIN, frontier, parse_queue)

    item = ParseItem(url="https://crawlme.monzo.com/", html=SAMPLE_HTML)
    await parser.process(item)

    # The frontier should now contain same-domain links only.
    queued_urls = set()
    while not frontier.empty:
        fi = await frontier.pop()
        queued_urls.add(fi.url)

    assert "https://crawlme.monzo.com/about" in queued_urls
    assert "https://crawlme.monzo.com/contact" in queued_urls
    assert "https://crawlme.monzo.com/faq" in queued_urls
    assert "https://facebook.com/monzo" not in queued_urls
    assert "https://monzo.com" not in queued_urls
    assert "https://community.monzo.com" not in queued_urls
