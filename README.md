# Web Crawler

An asynchronous, single-subdomain web crawler built in Python. Given a starting URL, it visits every page on the same subdomain, prints each visited URL with its discovered links, and produces a final results dictionary.

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
- **Fetcher Workers** — N concurrent workers (configurable) pull URLs, enforce per-worker rate-limiting and `robots.txt`, and fetch HTML. 404s are dropped immediately; other errors are retried with exponential backoff up to `max_retries`.
- **Parser Worker** — extracts HTTP/HTTPS links with BeautifulSoup (filtering out `mailto:`, `tel:`, etc.), enforces same-subdomain filtering, and pushes new URLs back to the frontier.

## Configuration

All settings live in [`config.yml`](config.yml):

```yaml
start_url: "https://crawlme.monzo.com/"
rate_limit: 0      # seconds between requests per fetcher (0 = no limit)
max_retries: 3     # retries before dropping a URL
num_fetchers: 30   # number of concurrent fetcher workers
```

The crawler also respects the target site's `robots.txt` — both `Disallow` rules and `Crawl-delay`.

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

The crawler will:
1. Print each visited URL and its found links as it goes.
2. Log queue sizes (frontier and parse) for observability.
3. On completion, save a `results.json` file where keys are visited URLs and values are arrays of links found on each page. A special `"Dropped sites"` key lists URLs that failed after all retries.

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- **Frontier** — deduplication, retry bypass, priority ordering
- **Parser** — link extraction, subdomain filtering, frontier push
- **Fetcher** — 404 dropping, successful fetch, retry scheduling, max-retries drop

## Project Structure

```
├── config.yml              # Crawl settings
├── pyproject.toml           # Dependencies & project metadata
├── src/
│   ├── main.py              # Orchestrator (entry point)
│   ├── config.py            # YAML config loader
│   ├── models.py            # FrontierItem & ParseItem dataclasses
│   ├── frontier.py          # PriorityQueue + seen-set
│   ├── fetcher.py           # Async fetcher with backoff
│   ├── parser.py            # HTML link extraction & filtering
│   └── utils/
│       └── robot.py         # robots.txt wrapper
└── tests/
    ├── test_frontier.py
    ├── test_parser.py
    └── test_fetcher.py
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| `asyncio.PriorityQueue` for frontier | Retry items carry a `scheduled_at` timestamp — the worker sleeps until backoff expires rather than spinning or using separate timers |
| Backoff encoded in the queue message | No in-memory timer needed; the frontier naturally processes items in time order |
| Configurable concurrent fetchers | Scale throughput by increasing `num_fetchers`; rate limit applies per worker |
| 404s dropped immediately | No point retrying a page the server says doesn't exist |
| `robots.txt` fetched once at startup | Single-seed crawl means one domain — no need to re-fetch |
| Subdomain filtering via `urlparse().netloc` | Strict match ensures `monzo.com` and `community.monzo.com` are excluded |
| Non-HTTP schemes filtered | `mailto:`, `tel:`, `javascript:` links are excluded from results |
