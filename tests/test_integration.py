"""Integration test — spins up a local HTTP server and runs the full crawl pipeline."""

import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from src.config import CrawlerConfig
from src.main import crawl


# Tiny local site served by Python's built-in HTTP server
PAGES = {
    "/": """
        <html><body>
            <a href="/about">About</a>
            <a href="/blog">Blog</a>
        </body></html>
    """,
    "/about": """
        <html><body>
            <a href="/">Home</a>
            <a href="/contact">Contact</a>
        </body></html>
    """,
    "/blog": """
        <html><body>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="https://external.com">External</a>
            <a href="mailto:hello@test.com">Email</a>
        </body></html>
    """,
    "/contact": """
        <html><body>
            <a href="/">Home</a>
        </body></html>
    """,
}


class LocalHandler(SimpleHTTPRequestHandler):
    """Serve pages from the PAGES dict."""

    def do_GET(self):
        path = self.path.split("?")[0]  # strip query strings

        if path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"User-agent: *\nAllow: /\n")
            return

        if path in PAGES:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGES[path].encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress request logs during tests


def start_server():
    """Start a local HTTP server in a background thread and return (server, port)."""
    server = HTTPServer(("127.0.0.1", 0), LocalHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


# Tests the full crawl pipeline
@pytest.mark.asyncio
async def test_full_crawl_pipeline():
    """Run the full crawl pipeline against a local HTTP server.

    Verifies that:
    - All reachable pages are visited.
    - External links appear in results but are not crawled.
    - Non-HTTP links (mailto:) appear in results but are not crawled.
    - No pages are dropped (all return 200).
    """
    server, port = start_server()
    base_url = f"http://127.0.0.1:{port}"

    try:
        config = CrawlerConfig(
            start_url=f"{base_url}/",
            rate_limit=0,
            max_retries=3,
            num_fetchers=10,
            max_concurrent=10,
            log_level="WARNING",
        )

        results = await crawl(config)

        # All 4 local pages should be visited.
        assert f"{base_url}/" in results
        assert f"{base_url}/about" in results
        assert f"{base_url}/blog" in results
        assert f"{base_url}/contact" in results

        # External link should appear in /blog's results but NOT as a visited page.
        blog_links = results[f"{base_url}/blog"]
        assert "https://external.com" in blog_links
        assert "https://external.com" not in results  # not crawled

        # mailto link should appear in /blog's results.
        assert "mailto:hello@test.com" in blog_links

        # No pages should be dropped (all return 200).
        assert results["Dropped sites"] == []

    finally:
        server.shutdown()


# Tests the crawl handles 404 pages
@pytest.mark.asyncio
async def test_crawl_handles_404():
    """Crawling a 404 page should drop it without crashing."""
    server, port = start_server()
    base_url = f"http://127.0.0.1:{port}"

    try:
        config = CrawlerConfig(
            start_url=f"{base_url}/does-not-exist",
            rate_limit=0,
            max_retries=1,
            num_fetchers=1,
            max_concurrent=1,
            log_level="WARNING",
        )

        results = await crawl(config)

        assert f"{base_url}/does-not-exist" in results["Dropped sites"]

    finally:
        server.shutdown()
