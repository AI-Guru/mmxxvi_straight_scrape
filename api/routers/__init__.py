from .search import router as search_router
from .fetch import router as fetch_router
from .health import router as health_router

__all__ = ["search_router", "fetch_router", "health_router"]
