import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext

from config import settings


class PlaywrightPool:
    def __init__(self, max_contexts: int | None = None):
        self.max_contexts = max_contexts or settings.playwright_max_contexts
        self.semaphore = asyncio.Semaphore(self.max_contexts)
        self._playwright = None
        self._browser: Browser | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.firefox.launch(
            headless=True,
            args=["--disable-gpu"]
        )
        self._initialized = True

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._initialized = False

    @asynccontextmanager
    async def get_context(self):
        if not self._initialized:
            await self.initialize()

        async with self.semaphore:
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
                    "Gecko/20100101 Firefox/121.0"
                ),
                java_script_enabled=True,
            )
            try:
                yield context
            finally:
                await context.close()


class Fetcher:
    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None
        self._playwright_pool = PlaywrightPool()

    async def initialize(self) -> None:
        self._http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
                    "Gecko/20100101 Firefox/121.0"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self._playwright_pool.close()

    def _needs_js_render(self, url: str, html: str | None) -> bool:
        if html is None:
            return True
        if len(html.strip()) < 500:
            return True

        js_indicators = [
            "please enable javascript",
            "javascript is required",
            "enable javascript to view",
            "requires javascript",
            "noscript",
            "__NEXT_DATA__",
            "window.__INITIAL_STATE__",
        ]
        html_lower = html.lower()
        for indicator in js_indicators:
            if indicator.lower() in html_lower:
                return True

        domain = urlparse(url).netloc.lower()
        for spa_domain in settings.spa_domains:
            if spa_domain in domain:
                return True

        return False

    async def _fast_fetch(self, url: str) -> tuple[str | None, str]:
        if not self._http_client:
            await self.initialize()

        try:
            response = await self._http_client.get(url)
            response.raise_for_status()
            canonical_url = str(response.url)
            return response.text, canonical_url
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None, url

    async def _js_fetch(self, url: str) -> tuple[str | None, str]:
        try:
            async with self._playwright_pool.get_context() as context:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                await asyncio.sleep(1)

                html = await page.content()
                canonical_url = page.url

                await page.close()
                return html, canonical_url
        except Exception:
            return None, url

    async def fetch(self, url: str, force_js: bool = False) -> tuple[str | None, str]:
        if force_js:
            return await self._js_fetch(url)

        html, canonical_url = await self._fast_fetch(url)

        if self._needs_js_render(url, html):
            js_html, js_url = await self._js_fetch(url)
            if js_html:
                return js_html, js_url

        return html, canonical_url


fetcher = Fetcher()
