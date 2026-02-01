import httpx
from urllib.parse import urljoin

from config import settings


class SearXNGClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.searxng_url
        self._client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            follow_redirects=True
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        max_results: int = 10,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        language: str = "en"
    ) -> list[dict]:
        if not self._client:
            await self.initialize()

        params = {
            "q": query,
            "format": "json",
            "language": language,
        }

        if engines:
            params["engines"] = ",".join(engines)
        if categories:
            params["categories"] = ",".join(categories)

        try:
            response = await self._client.get("/search", params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"SearXNG search failed: {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"SearXNG connection error: {str(e)}")

        results = []
        for item in data.get("results", [])[:max_results]:
            result = {
                "url": self._resolve_redirects(item.get("url", "")),
                "title": item.get("title", ""),
                "snippet": item.get("content", ""),
                "engine": item.get("engine", ""),
                "score": item.get("score", 0.0),
            }
            if result["url"]:
                results.append(result)

        return results

    def _resolve_redirects(self, url: str) -> str:
        if not url:
            return url

        redirect_patterns = [
            "google.com/url?",
            "bing.com/ck/a?",
            "duckduckgo.com/l/?",
        ]

        for pattern in redirect_patterns:
            if pattern in url:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if "url" in params:
                    return params["url"][0]
                if "u" in params:
                    return params["u"][0]
                if "uddg" in params:
                    return params["uddg"][0]

        return url


searxng_client = SearXNGClient()
