import trafilatura
from readability import Document
import html2text


def extract_with_trafilatura(html: str, url: str) -> str | None:
    try:
        content = trafilatura.extract(
            html,
            url=url,
            include_links=True,
            include_tables=True,
            include_images=False,
            include_comments=False,
            output_format="markdown",
            favor_precision=True,
        )
        return content if content and len(content.strip()) > 100 else None
    except Exception:
        return None


def extract_with_readability(html: str) -> str | None:
    try:
        doc = Document(html)
        summary = doc.summary()

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        h.unicode_snob = True

        content = h.handle(summary)
        return content if content and len(content.strip()) > 100 else None
    except Exception:
        return None


def extract_content(html: str, url: str) -> str:
    content = extract_with_trafilatura(html, url)

    if not content:
        content = extract_with_readability(html)

    if not content:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        try:
            content = h.handle(html)
            if content:
                content = content[:50000]
        except Exception:
            content = ""

    return content or ""
