"""
Input ingestion utilities for resume files and job URLs.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urlparse

import httpx
from docx import Document
from pypdf import PdfReader

_BULLET_START  = re.compile(r"^[●•\-–—]")
_ALLCAPS_START = re.compile(r"^[A-Z][A-Z\s&/,]{3,}")
_COLON_END     = re.compile(r"\w.*:$")
_DATE_START    = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}")


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


def _is_new_block(line: str) -> bool:
    """Return True if this line should NOT be merged with the previous one."""
    return bool(
        _BULLET_START.match(line)
        or _ALLCAPS_START.match(line)
        or _COLON_END.match(line)
        or _DATE_START.match(line)
    )


def _is_fragment(line: str) -> bool:
    """Short word-sequence that is likely a PDF column layout artefact, not a standalone block."""
    if not line or _is_new_block(line):
        return False
    words = line.split()
    return len(words) <= 3 and not line.endswith(".")


def _normalize_pdf(raw: str) -> str:
    """
    Clean PDF-extracted text that comes out word-per-line due to column layout.

    Steps:
    1. Collapse multiple spaces → single space.
    2. Strip each line.
    3. Remove blank lines that are sandwiched between short fragments
       (e.g. "APIs,\\n\\nand\\n\\ndatabases" → "APIs, and databases").
    4. Merge short-fragment continuation lines and lowercase-starting lines
       into the previous line, unless the previous line ends a sentence.
    5. Collapse consecutive blank lines.
    """
    raw = re.sub(r"[ \t]{2,}", " ", raw)
    lines = [line.strip() for line in raw.splitlines()]

    # Pass 1 — remove blank lines between fragments so the merge pass can see them as adjacent
    deblocked: list[str] = []
    n = len(lines)
    for i, line in enumerate(lines):
        if line == "":
            prev = lines[i - 1].strip() if i > 0 else ""
            nxt  = lines[i + 1].strip() if i + 1 < n else ""
            # Skip blank if either neighbour is a short fragment
            if _is_fragment(prev) or _is_fragment(nxt):
                continue
        deblocked.append(line)

    # Pass 2 — merge continuation lines
    merged: list[str] = []
    for line in deblocked:
        if not line:
            merged.append("")
            continue
        if (
            merged
            and merged[-1]
            and not _is_new_block(line)
            and not merged[-1].endswith((".", ":", "–", "—", "|"))
            and (line[0].islower() or line[0] in ",;)(" or _is_fragment(line))
        ):
            merged[-1] = merged[-1] + " " + line
        else:
            merged.append(line)

    # Pass 3 — collapse consecutive blank lines
    result: list[str] = []
    prev_blank = False
    for line in merged:
        if not line:
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    return "\n".join(result).strip()


async def extract_resume_text(filename: str, content: bytes) -> str:
    lower_name = (filename or "").lower()
    if lower_name.endswith(".txt"):
        return _normalize_text(content.decode("utf-8", errors="ignore"))

    if lower_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        page_text = [page.extract_text() or "" for page in reader.pages]
        return _normalize_pdf("\n".join(page_text))

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
