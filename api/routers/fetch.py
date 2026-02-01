import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from cache import cache
from models.schemas import FetchRequest, FetchResponse, DiffRequest, DiffResponse
from services.fetcher import fetcher
from services.extractor import extract_content
from services.summarizer import summarizer

router = APIRouter(prefix="/api", tags=["fetch"])


@router.post("/fetch", response_model=FetchResponse)
async def fetch_url(request: FetchRequest) -> FetchResponse:
    previous_hash = await cache.get_content_hash(request.url)

    if not request.bypass_cache:
        cached = await cache.get_content(request.url)
        if cached:
            response = FetchResponse(
                url=request.url,
                canonical_url=cached["canonical_url"],
                markdown=cached["markdown"],
                fetched_at=datetime.fromtimestamp(
                    cached["fetched_at"], tz=timezone.utc
                ),
                from_cache=True,
                content_hash=cached["content_hash"],
                changed_since_last=None,
            )

            if request.summarize:
                response.summary = await summarizer.summarize(cached["markdown"])

            return response

    html, canonical_url = await fetcher.fetch(request.url, force_js=request.force_js)

    if not html:
        raise HTTPException(status_code=502, detail="Failed to fetch URL")

    markdown = extract_content(html, request.url)
    if not markdown:
        raise HTTPException(status_code=422, detail="Failed to extract content")

    content_hash = cache.hash_content(markdown)
    now = datetime.now(timezone.utc)

    await cache.set_content(request.url, canonical_url, markdown)

    summary = None
    if request.summarize:
        summary = await summarizer.summarize(markdown)

    return FetchResponse(
        url=request.url,
        canonical_url=canonical_url,
        markdown=markdown,
        summary=summary,
        fetched_at=now,
        from_cache=False,
        content_hash=content_hash,
        changed_since_last=previous_hash is not None and previous_hash != content_hash,
    )


@router.post("/diff", response_model=DiffResponse)
async def check_diff(request: DiffRequest) -> DiffResponse:
    previous_hash = await cache.get_content_hash(request.url)

    html, canonical_url = await fetcher.fetch(request.url)

    if not html:
        raise HTTPException(status_code=502, detail="Failed to fetch URL")

    markdown = extract_content(html, request.url)
    current_hash = cache.hash_content(markdown)
    now = datetime.now(timezone.utc)

    await cache.set_content(request.url, canonical_url, markdown)

    return DiffResponse(
        url=request.url,
        changed=previous_hash is not None and previous_hash != current_hash,
        previous_hash=previous_hash,
        current_hash=current_hash,
        last_checked=now,
    )
