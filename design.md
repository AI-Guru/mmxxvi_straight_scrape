# Local Web Research API

A self-hosted Tavily alternative for multi-agent systems requiring up-to-date web content retrieval and extraction.

## Project Goal

Build a local API service that:
- Accepts research queries from multiple agents
- Searches the web via SearXNG (self-hosted metasearch)
- Fetches and renders pages (including JS-heavy SPAs)
- Extracts clean markdown content
- Returns structured, cached results

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│     Agents      │────▶│   Research API  │────▶│     SearXNG      │
│  (MAS clients)  │     │   (FastAPI)     │     │  (Docker/local)  │
└─────────────────┘     └────────┬────────┘     └──────────────────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │  Fetch Layer   │
                        │  ┌──────────┐  │
                        │  │  httpx   │◀─┼─── Fast path (~80% of requests)
                        │  └──────────┘  │
                        │  ┌──────────┐  │
                        │  │Playwright│◀─┼─── JS render path (~20%)
                        │  └──────────┘  │
                        └────────┬───────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │   Extractor    │
                        │  (Trafilatura) │
                        └────────┬───────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │     Cache      │
                        │ (SQLite/Redis) │
                        └────────────────┘
```

---

## Components

### 1. SearXNG (Search Layer)

**Why SearXNG over raw DuckDuckGo scraping:**
- Native JSON API (no HTML parsing)
- Source redundancy (DDG, Brave, Qwant, etc.)
- Self-hosted control over result count and engine selection
- No external API costs or rate limit concerns

**Deployment:**
```bash
docker run -d -p 8080:8080 searxng/searxng
```

**Configuration notes:**
- Enable JSON output format
- Configure engine weights based on query types
- Disable engines that add tracking redirects to URLs

**Edge case:** SearXNG result URLs sometimes pass through redirect wrappers. Implement redirect resolution before caching to avoid duplicate entries for the same destination.

---

### 2. Fetch Layer (Tiered Strategy)

Do not use Playwright for every request. Implement a two-tier approach:

#### Fast Path: httpx
- Use for ~80% of pages
- Sub-second response times
- Minimal resource overhead

```python
async def fast_fetch(url: str) -> str | None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(url)
        return resp.text if resp.status_code == 200 else None
```

#### Slow Path: Playwright
- Use only when JS rendering is required
- Manage a browser context pool (limit concurrency to control memory)
- Each context ~200-500MB RAM

```python
def needs_js_render(url: str, fast_result: str | None) -> bool:
    if fast_result is None:
        return True
    if len(fast_result.strip()) < 500:
        return True
    if "please enable javascript" in fast_result.lower():
        return True
    if is_known_spa_domain(url):
        return True
    return False
```

**Known SPA domains (starter list):**
- Medium, Substack (partial)
- Most React/Vue/Angular apps
- Sites behind Cloudflare JS challenge

**Playwright configuration:**
```python
# Use Firefox or WebKit to reduce fingerprinting
browser = await playwright.firefox.launch(headless=True)
context = await browser.new_context(
    viewport={"width": 1280, "height": 720},
    user_agent="Mozilla/5.0 ..."
)
```

---

### 3. Content Extraction

**Primary: Trafilatura**
- Best balance of speed and accuracy for article extraction
- Handles boilerplate removal well
- Returns clean text

```python
import trafilatura

def extract_content(html: str, url: str) -> str:
    return trafilatura.extract(
        html,
        url=url,
        include_links=True,
        include_tables=True,
        output_format="markdown"
    ) or ""
```

**Fallback: readability-lxml + html2text**
- For pages where Trafilatura yields thin results
- Better at preserving structure (headers, lists, code blocks)

```python
from readability import Document
import html2text

def extract_with_readability(html: str) -> str:
    doc = Document(html)
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    return h.handle(doc.summary())
```

---

### 4. Caching Strategy

**Two-layer cache:**

| Layer | Key | TTL | Purpose |
|-------|-----|-----|---------|
| Search results | `hash(query + engines)` | 15-30 min | Avoid repeated searches |
| Page content | `canonical_url` | 2-24 hours | Avoid repeated fetches |

**Implementation (SQLite for local use):**

```sql
CREATE TABLE search_cache (
    query_hash TEXT PRIMARY KEY,
    results JSON,
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE TABLE content_cache (
    url_hash TEXT PRIMARY KEY,
    canonical_url TEXT,
    markdown TEXT,
    fetched_at TIMESTAMP,
    expires_at TIMESTAMP,
    content_hash TEXT  -- for change detection
);
```

**Cache invalidation:**
- Explicit bust via API parameter
- Content hash comparison for change detection
- Respect `Cache-Control` headers when present

---

## API Design

### Endpoints

#### `POST /search`
Basic search and extract.

```json
// Request
{
  "query": "CUDA 13 new features",
  "max_results": 5,
  "extract": true,
  "bypass_cache": false
}

// Response
{
  "query": "CUDA 13 new features",
  "results": [
    {
      "url": "https://...",
      "title": "...",
      "snippet": "...",
      "markdown": "...",
      "fetched_at": "2025-02-01T12:00:00Z",
      "from_cache": true
    }
  ],
  "search_time_ms": 450,
  "extract_time_ms": 1200
}
```

#### `POST /fetch`
Direct URL fetch (when agent already knows what it wants).

```json
// Request
{
  "url": "https://example.com/article",
  "force_js": false,
  "bypass_cache": false
}

// Response
{
  "url": "https://example.com/article",
  "canonical_url": "https://example.com/article/",
  "markdown": "...",
  "fetched_at": "...",
  "changed_since_last": false
}
```

#### `POST /diff`
Check if content has changed since last fetch.

```json
// Request
{
  "url": "https://example.com/article",
  "since": "2025-01-15T00:00:00Z"
}

// Response
{
  "url": "https://example.com/article",
  "changed": true,
  "previous_hash": "abc123",
  "current_hash": "def456",
  "last_checked": "2025-02-01T12:00:00Z"
}
```

#### `GET /health`
Service health check for agents.

---

## Multi-Agent Considerations

### Request Deduplication
When multiple agents search similar queries concurrently:

```python
import asyncio
from collections import defaultdict

_pending: dict[str, asyncio.Future] = {}

async def deduplicated_search(query: str) -> SearchResult:
    key = normalize_query(query)
    if key in _pending:
        return await _pending[key]
    
    future = asyncio.get_event_loop().create_future()
    _pending[key] = future
    try:
        result = await _do_search(query)
        future.set_result(result)
        return result
    finally:
        del _pending[key]
```

### Shared Context Accumulation
Consider exposing a session-based "knowledge base" that accumulates fetched content:

```json
// POST /session
{ "session_id": "task-123" }

// POST /search with session
{
  "query": "...",
  "session_id": "task-123"  // results added to session KB
}

// GET /session/task-123/context
// Returns all accumulated content for this task
```

This prevents agents from redundantly fetching the same pages when working on related subtasks.

---

## Resource Management

### Playwright Pool

```python
from contextlib import asynccontextmanager
import asyncio

class PlaywrightPool:
    def __init__(self, max_contexts: int = 3):
        self.semaphore = asyncio.Semaphore(max_contexts)
        self.browser = None
    
    async def initialize(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
    
    @asynccontextmanager
    async def get_context(self):
        async with self.semaphore:
            context = await self.browser.new_context()
            try:
                yield context
            finally:
                await context.close()
```

**Memory budget guidelines:**
- 3 concurrent contexts ≈ 1.5-2GB RAM
- 5 concurrent contexts ≈ 2.5-3GB RAM
- Scale based on available resources

---

## Tech Stack Summary

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | FastAPI | Async-native, good typing, auto docs |
| Search | SearXNG | Self-hosted, multi-engine, JSON API |
| HTTP client | httpx | Async, HTTP/2, good timeout handling |
| JS rendering | Playwright | Multi-browser, Python-native, good stealth |
| Extraction | Trafilatura | Fast, accurate, markdown output |
| Cache | SQLite (local) / Redis (distributed) | Simple, no external deps for local |
| Serialization | orjson | Fast JSON for high-throughput |

---

## Directory Structure

```
local-web-research-api/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app
│   │   ├── routes.py        # Endpoint definitions
│   │   └── models.py        # Pydantic schemas
│   ├── search/
│   │   ├── __init__.py
│   │   └── searxng.py       # SearXNG client
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── fast.py          # httpx fetcher
│   │   ├── js.py            # Playwright fetcher
│   │   └── pool.py          # Browser pool management
│   ├── extract/
│   │   ├── __init__.py
│   │   └── markdown.py      # Content extraction
│   ├── cache/
│   │   ├── __init__.py
│   │   └── sqlite.py        # Cache implementation
│   └── utils/
│       ├── __init__.py
│       ├── dedup.py         # Request deduplication
│       └── urls.py          # URL normalization
├── tests/
├── docker-compose.yml       # App + SearXNG
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## Getting Started (for Claude Code)

1. **Set up SearXNG:**
   ```bash
   docker run -d --name searxng -p 8080:8080 searxng/searxng
   ```

2. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn httpx playwright trafilatura orjson aiosqlite
   playwright install firefox
   ```

3. **Implement in order:**
   - Cache layer (SQLite)
   - SearXNG client
   - Fast fetch (httpx)
   - Content extraction (Trafilatura)
   - API routes (basic /search, /fetch)
   - Playwright pool + JS rendering
   - Request deduplication
   - /diff endpoint

4. **Test with:**
   ```bash
   uvicorn src.api.main:app --reload
   curl -X POST http://localhost:8000/search \
     -H "Content-Type: application/json" \
     -d '{"query": "python asyncio tutorial", "max_results": 3}'
   ```

---

## Open Questions for Implementation

1. **Rate limiting:** Should the API enforce per-agent rate limits, or trust agents to self-regulate?

2. **Result ranking:** Should the API expose a reranking option, or return raw search order?

3. **Error handling:** On partial failures (3/5 URLs fetched successfully), return partial results or fail entirely?

4. **Persistence:** Should session knowledge bases persist across service restarts?