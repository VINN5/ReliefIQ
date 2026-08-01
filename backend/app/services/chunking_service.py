"""
Chunking service — turns a document's extracted pages into retrievable
chunks, split on logical boundaries (headings, paragraphs) rather than
a fixed token count.

Heuristic, not perfect: raw extracted PDF text has no font/bold/heading
markup, so "heading detection" is pattern-based (short lines, numbered
sections, title case, no trailing punctuation). Works well on structured
policy documents; won't be flawless on every layout.

Noise handling, two layers:
1. Full-line boilerplate: short lines repeated across many pages
   (exact match) are dropped entirely.
2. Glued headers: some PDFs render a running header directly onto the
   same line as body text, with no space (e.g. "2 | CHOLERA WASH
   RESPONSEtrained and equipped..."). These are detected generically by
   looking for a leading run of uppercase letters/digits/punctuation
   that recurs across pages (page numbers normalized to a placeholder
   so they still count as "the same" header), then stripped as a prefix
   — regardless of the header's exact wording, so this isn't limited to
   one specific document's format.

Security: every finalized chunk also passes through
content_safety.strip_prompt_injection() before being returned — this
is the PRIMARY point where prompt-injection content gets stripped from
a document (see content_safety.py's docstring for why it's here rather
than only at query time).
"""

import re
from collections import Counter
from dataclasses import dataclass

from app.services.content_safety import strip_prompt_injection

MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 1500
REPEATED_LINE_MAX_LENGTH = 60
REPEATED_LINE_MIN_FRACTION = 0.3  # appears on 30%+ of pages -> boilerplate

_HEADING_PATTERNS = [
    re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z].{0,80}$"),  # "1. Introduction", "2.1 Scope"
    re.compile(r"^[A-Z][A-Z\s\d,&/-]{4,80}$"),        # ALL CAPS headings
    re.compile(r"^(Section|Chapter|Appendix)\s+\d+.{0,80}$", re.IGNORECASE),
]

_PAGE_NUMBER_PATTERN = re.compile(
    r"^\s*(page\s*\|?\s*\d+(\s*(/|of)\s*\d+)?)\s*", re.IGNORECASE
)

# Leading run of caps/digits/punctuation, stopping right before the
# first lowercase letter — catches glued running headers regardless of
# their exact wording.
_LEADING_RUN_PATTERN = re.compile(r"^([A-Z0-9\s\|/\-.,:]{3,80})(?=[a-z])")


@dataclass
class Chunk:
    content: str
    page_number: int | None
    section_heading: str | None


def _normalize_run(run: str) -> str:
    """Collapses digits and whitespace so 'Page 2 |' and 'Page 3 |' count as the same recurring header."""
    normalized = re.sub(r"\d+", "#", run)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _find_boilerplate_lines(pages: list[dict]) -> set[str]:
    """
    Detects header/footer text by frequency: short lines repeated across
    many pages are almost certainly boilerplate, not content.
    """
    total_pages = len(pages) or 1
    counts: Counter[str] = Counter()

    for page in pages:
        text = page.get("text") or ""
        lines_on_page = {
            line.strip()
            for line in text.split("\n")
            if line.strip() and len(line.strip()) <= REPEATED_LINE_MAX_LENGTH
        }
        for line in lines_on_page:
            counts[line] += 1

    threshold = max(2, total_pages * REPEATED_LINE_MIN_FRACTION)
    return {line for line, count in counts.items() if count >= threshold}


def _find_glued_header_prefixes(pages: list[dict]) -> set[str]:
    """
    Detects recurring header text glued directly onto body text with no
    separating space, by finding leading caps/digit/punctuation runs
    that recur across the document (page numbers normalized away so
    "2 | X" and "4 | X" count as the same header).

    Uses a low absolute threshold rather than a fraction of total pages:
    unlike per-page footers, this kind of glued header often only
    appears at chapter/section starts, so it may occur just a handful
    of times across a long document.
    """
    counts: Counter[str] = Counter()

    for page in pages:
        text = page.get("text") or ""
        seen_on_page = set()
        for line in text.split("\n"):
            match = _LEADING_RUN_PATTERN.match(line)
            if not match:
                continue
            run = match.group(1)
            remainder = line[len(run):]
            if len(remainder) < 10:
                continue
            seen_on_page.add(_normalize_run(run))
        for normalized in seen_on_page:
            counts[normalized] += 1

    return {normalized for normalized, count in counts.items() if count >= 2}


def _strip_boilerplate(text: str, boilerplate: set[str]) -> str:
    kept_lines = []
    for line in text.split("\n"):
        line = _PAGE_NUMBER_PATTERN.sub("", line)
        stripped = line.strip()
        if not stripped or stripped in boilerplate:
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def _strip_glued_headers(text: str, glued_headers: set[str]) -> str:
    stripped_lines = []
    for line in text.split("\n"):
        match = _LEADING_RUN_PATTERN.match(line)
        if match:
            run = match.group(1)
            if _normalize_run(run) in glued_headers:
                line = line[len(run):]
        stripped_lines.append(line)
    return "\n".join(stripped_lines)


def _looks_like_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 90 or line.endswith((".", ",", ";", ":")):
        return False
    return any(pattern.match(line) for pattern in _HEADING_PATTERNS)


def _split_into_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_pages(pages: list[dict]) -> list[Chunk]:
    """
    pages: [{"page": int | None, "text": str}, ...] — matches
    Document.extracted_pages exactly.
    """
    boilerplate = _find_boilerplate_lines(pages)
    glued_headers = _find_glued_header_prefixes(pages)

    raw_chunks: list[Chunk] = []
    current_heading: str | None = None

    for page in pages:
        page_number = page.get("page")
        text = _strip_boilerplate(page.get("text") or "", boilerplate)
        text = _strip_glued_headers(text, glued_headers)

        for paragraph in _split_into_paragraphs(text):
            lines = paragraph.split("\n")
            if len(lines) == 1 and _looks_like_heading(lines[0]):
                current_heading = lines[0].strip()
                continue

            raw_chunks.append(
                Chunk(content=paragraph, page_number=page_number, section_heading=current_heading)
            )

    final_chunks = _normalize_chunk_sizes(raw_chunks)

    # Primary prompt-injection defense — see module docstring. Applied
    # once per finalized chunk (after merging/splitting) rather than per
    # raw paragraph, so it only needs to run over the final content that
    # actually gets stored, not intermediate pieces that may get merged
    # away.
    return [
        Chunk(
            content=strip_prompt_injection(chunk.content, source="ingestion"),
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
        )
        for chunk in final_chunks
    ]


def _normalize_chunk_sizes(chunks: list[Chunk]) -> list[Chunk]:
    """
    Merges undersized chunks into their neighbor, splits oversized ones.
    Merging is allowed across a page boundary as long as the section
    heading matches — a paragraph continuing onto the next page
    shouldn't be split just because the page number changed. The
    merged chunk keeps the FIRST chunk's page number, since that's
    where the cited content begins.
    """
    merged: list[Chunk] = []
    buffer: Chunk | None = None

    for chunk in chunks:
        if buffer is None:
            buffer = chunk
            continue

        same_section = buffer.section_heading == chunk.section_heading
        if len(buffer.content) < MIN_CHUNK_CHARS and same_section:
            buffer.content = f"{buffer.content}\n\n{chunk.content}"
        else:
            merged.append(buffer)
            buffer = chunk

    if buffer is not None:
        merged.append(buffer)

    final: list[Chunk] = []
    for chunk in merged:
        final.extend(_split_oversized(chunk))
    return final


def _split_oversized(chunk: Chunk) -> list[Chunk]:
    if len(chunk.content) <= MAX_CHUNK_CHARS:
        return [chunk]

    sentences = re.split(r"(?<=[.!?])\s+", chunk.content)
    pieces: list[Chunk] = []
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) > MAX_CHUNK_CHARS and buffer:
            pieces.append(Chunk(buffer.strip(), chunk.page_number, chunk.section_heading))
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        pieces.append(Chunk(buffer.strip(), chunk.page_number, chunk.section_heading))
    return pieces