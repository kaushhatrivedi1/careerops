"""
Input ingestion utilities for resume files and job URLs.
"""
from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlparse

import httpx
from docx import Document
from pypdf import PdfReader


_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "li"}
_BLOCK_TAGS = {"p", "div", "section", "article", "header", "footer", "ul", "ol", "br", "tr", "td"}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []
        self._pending_newline = False

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag in _HEADING_TAGS:
            # Add double newline before headings so section detection works
            self._chunks.append("\n\n")
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in _HEADING_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._skip_depth == 0:
            cleaned = " ".join(data.split())
            if cleaned:
                self._chunks.append(cleaned)

    def text(self) -> str:
        return "".join(self._chunks)


def _normalize_text(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


async def extract_resume_text(filename: str, content: bytes) -> str:
    lower_name = (filename or "").lower()
    if lower_name.endswith(".txt"):
        return _normalize_text(content.decode("utf-8", errors="ignore"))

    if lower_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        page_text = [page.extract_text() or "" for page in reader.pages]
        return _normalize_text("\n".join(page_text))

    if lower_name.endswith(".docx"):
        doc = Document(BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs]
        return _normalize_text("\n".join(paragraphs))

    raise ValueError("Unsupported resume format. Use .pdf, .docx, or .txt.")


def _validate_url(job_url: str) -> None:
    parsed = urlparse(job_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid job URL. Use a full http/https URL.")


async def fetch_job_text_from_url(job_url: str) -> str:
    _validate_url(job_url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = await client.get(job_url)
        response.raise_for_status()
        html = response.text

    parser = _VisibleTextParser()
    parser.feed(html)
    parser.close()
    text = _normalize_text(parser.text())
    if not text:
        raise ValueError("Could not extract readable text from the provided job URL.")
    return text
