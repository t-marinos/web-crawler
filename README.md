# Web Crawler

An asynchronous, single-subdomain web crawler built in Python. Given a starting URL, it visits every page on the same subdomain, prints each visited URL with its discovered links, and produces a final results dictionary with all the links found on each page.

The crawler will:
1. Log each visited URL and its found links.
2. Log queue sizes (frontier and parse) for observability.
3. On completion, save a `results.json` file where keys are visited URLs and values are arrays of links found on each page. A special `"Dropped sites"` key lists URLs that failed after all retries.

## Architecture

The crawler uses a **two-queue pipeline**:

```
Frontier Queue (PriorityQueue)
       │
       ▼
  Fetcher Workers (N) ──▶ Parse Queue ──▶ Parser Worker
       │                                       │
       │ (retry / drop)             (new same-domain links)
       ▼                                       │
  Dropped Sites                       ┌────────┘
                                      ▼
                              Frontier Queue (loop)
```

- **Frontier Queue** — `asyncio.PriorityQueue` ordered by `scheduled_at`, enabling exponential backoff without blocking.
- **Fetcher Workers** — Concurrent workers (configurable) pull URLs, enforce concurrency limits via a shared semaphore, respect `robots.txt` rules and `Crawl-delay`, and fetch HTML. 404s are dropped immediately; other errors are retried with exponential backoff up to `max_retries`.
- **Parse Queue** — `asyncio.Queue` that holds the HTML content of the fetched pages.
- **Parser Worker** — extracts links with BeautifulSoup, enforces same subdomain + HTTP(S) filtering via `is_same_domain`, and pushes new URLs back to the frontier. Non-HTTP links (`mailto:`, `tel:`) appear in results but are never queued.

## Configuration

All settings are defined in [`config.yml`](config.yml):

## Setup

```bash
# Install (production only)
pip install .

# Install with dev/test dependencies
pip install ".[dev]"
```

Requires Python ≥ 3.10.

## Usage

```bash
python -m src.main
```

## Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```