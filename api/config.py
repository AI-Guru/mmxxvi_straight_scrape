from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SearXNG Configuration
    searxng_url: str = "http://searxng:8080"

    # Ollama Configuration
    ollama_host: str = "http://host.docker.internal:11434"
    ollama_model: str = "gpt-oss:20b"

    # Cache Configuration
    cache_dir: str = "/app/data"
    cache_ttl_search: int = 1800  # 30 minutes
    cache_ttl_content: int = 86400  # 24 hours

    # Playwright Configuration
    playwright_max_contexts: int = 3

    # Known SPA domains that require JS rendering
    spa_domains: list[str] = [
        "medium.com",
        "substack.com",
        "notion.so",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
