from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from cache import cache
from services.searxng import searxng_client
from services.fetcher import fetcher
from services.summarizer import summarizer
from routers import search_router, fetch_router, health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.initialize()
    await searxng_client.initialize()
    await fetcher.initialize()
    await summarizer.initialize()

    yield

    await summarizer.close()
    await fetcher.close()
    await searxng_client.close()
    await cache.close()


app = FastAPI(
    title="Web Scrape API",
    description="Self-hosted web research and content extraction API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(fetch_router)
app.include_router(health_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/api/status")
async def status():
    return {"status": "ok"}
