"""
Extraction service — the ONLY module that knows how to pull text out of
a source file. Callers (the ingestion worker) just call `extract()` and
get back page-level text; they don't need to know PDF vs DOCX internals.

Note on page numbers: PDFs have real, fixed pages, so we extract true
page numbers. DOCX files do NOT — Word paginates dynamically at render
time, so there's no page boundary stored in the .docx file itself. DOCX
pages are returned with page_number=None; page-level citation for DOCX
sources isn't possible until we render them, which is out of scope here.
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument


@dataclass
class ExtractedPage:
    page_number: int | None
    text: str


def extract_pdf(file_path: str) -> list[ExtractedPage]:
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(ExtractedPage(page_number=i, text=text.strip()))
    return pages


def extract_docx(file_path: str) -> list[ExtractedPage]:
    doc = DocxDocument(file_path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [ExtractedPage(page_number=None, text=text.strip())]


def extract(file_path: str, doc_type: str | None) -> list[ExtractedPage]:
    suffix = (doc_type or Path(file_path).suffix.lstrip(".")).lower()
    if suffix == "pdf":
        return extract_pdf(file_path)
    if suffix == "docx":
        return extract_docx(file_path)
    raise ValueError(f"Unsupported doc_type for extraction: '{suffix}'")


def is_extraction_empty(pages: list[ExtractedPage]) -> bool:
    """
    True if effectively no text came out — the signal that a PDF is
    likely scanned/image-based and needs OCR (not handled yet).
    """
    total_chars = sum(len(p.text) for p in pages)
    return total_chars < 20