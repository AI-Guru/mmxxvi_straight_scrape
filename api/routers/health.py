from fastapi import APIRouter
import httpx

from config import settings
from models.schemas import HealthResponse
from services.summarizer import summarizer
from services.fetcher import fetcher

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    searxng_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.searxng_url}/healthz")
            searxng_ok = response.status_code == 200
    except Exception:
        pass

    ollama_ok = await summarizer.is_available()

    playwright_contexts = settings.playwright_max_contexts

    return HealthResponse(
        status="healthy" if searxng_ok else "degraded",
        searxng=searxng_ok,
        ollama=ollama_ok,
        playwright_contexts=playwright_contexts,
    )
