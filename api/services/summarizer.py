import ollama

from config import settings


class Summarizer:
    def __init__(self, host: str | None = None, model: str | None = None):
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self._client: ollama.AsyncClient | None = None

    async def initialize(self) -> None:
        self._client = ollama.AsyncClient(host=self.host)

    async def close(self) -> None:
        self._client = None

    async def summarize(
        self,
        content: str,
        max_length: int = 500,
        focus: str | None = None
    ) -> str:
        if not self._client:
            await self.initialize()

        content_preview = content[:10000]

        if focus:
            prompt = f"""Summarize the following web content, focusing on: {focus}

Keep the summary concise (under {max_length} words) and informative.
Focus on key facts, main points, and relevant details.
If the content doesn't relate to the focus topic, mention that briefly.

Content:
{content_preview}

Summary:"""
        else:
            prompt = f"""Summarize the following web content concisely (under {max_length} words).
Focus on the main points, key facts, and important details.
Write in clear, direct prose.

Content:
{content_preview}

Summary:"""

        try:
            response = await self._client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that summarizes web content clearly and concisely."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                options={
                    "temperature": 0.3,
                    "num_predict": max_length * 2,
                }
            )
            return response["message"]["content"].strip()
        except Exception as e:
            return f"[Summarization failed: {str(e)}]"

    async def is_available(self) -> bool:
        if not self._client:
            try:
                await self.initialize()
            except Exception:
                return False

        try:
            await self._client.list()
            return True
        except Exception:
            return False


summarizer = Summarizer()
