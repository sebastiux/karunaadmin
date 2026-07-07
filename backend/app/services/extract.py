"""Best-effort text extraction from uploaded documents.

Supports PDF, DOCX, and plain text / markdown. Any other file type is accepted
and stored, but yields no extracted text (returns ""). Failures never raise —
extraction is a convenience for feeding the AI, not a hard requirement.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger("extract")


def extract_text(filename: str, content_type: str, data: bytes) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    try:
        if name.endswith(".pdf") or "pdf" in ctype:
            return _pdf(data)
        if name.endswith(".docx") or "wordprocessingml" in ctype:
            return _docx(data)
        if name.endswith((".txt", ".md", ".csv", ".json")) or ctype.startswith("text/"):
            return data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 — never break an upload over parsing
        logger.warning("Text extraction failed for %s: %s", filename, exc)
    return ""


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts).strip()


def _docx(data: bytes) -> str:
    import docx  # python-docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs).strip()
