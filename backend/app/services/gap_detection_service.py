"""
Gap detection service — given a donor's policy document (or pasted
text), figures out which of its requirements the organisation's own
internal policies already cover, and which are gaps.

Deliberately NOT part of the document ingestion pipeline: a donor
policy uploaded here is a one-off comparison input, not something that
becomes part of the organisation's own searchable knowledge base. It's
never chunked, embedded, or stored — text is extracted, used for this
one analysis, and discarded.

Pipeline per analysis:
  1. Get donor policy text (from an uploaded PDF or pasted text).
  2. Split it into individual requirement-sized clauses.
  3. For each requirement, retrieve the most similar internal-policy
     chunks (same retrieval_service used everywhere else — including
     the same RBAC filtering, so gap detection can never surface
     restricted internal content to a role that shouldn't see it).
  4. Ask the LLM to classify each requirement as COVERED / PARTIAL / GAP
     against those chunks.
  5. Summarize with plain counts — no LLM call for the summary, since a
     count is unambiguous and doesn't need to be "generated."

Requirement count is capped (see MAX_REQUIREMENTS) to keep a single
analysis bounded in cost and latency — a 40-page donor policy could
otherwise mean 100+ sequential LLM calls.
"""

import io
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.generation_service import CoverageStatus, assess_requirement_coverage
from app.services.retrieval_service import search_similar_chunks

logger = logging.getLogger(__name__)

MAX_REQUIREMENTS = 25
MIN_REQUIREMENT_LENGTH = 20  # characters — filters out stray short lines/headers
CHUNKS_PER_REQUIREMENT = 3


@dataclass
class GapItem:
    requirement: str
    status: CoverageStatus
    explanation: str
    matched_documents: list[str] = field(default_factory=list)


@dataclass
class GapAnalysisResult:
    items: list[GapItem]
    covered_count: int
    partial_count: int
    gap_count: int
    total_requirements: int
    summary: str
    truncated: bool  # True if the donor document had more requirements than MAX_REQUIREMENTS


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Standalone PDF text extraction for gap detection's one-off input.
    Deliberately separate from the main ingestion pipeline (which
    persists extracted_pages, handles OCR fallback, etc.) — this is a
    throwaway extraction for a document that's never stored.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages_text)


# Matches common list markers at the start of a line: "1.", "1)", "(1)",
# "a)", "-", "*", "•", plus a generic single-punctuation-mark fallback
# (`[^\w\s]\s+`). That last branch exists because PDF text extraction
# frequently turns bullet glyphs into unpredictable characters (private-use
# Unicode codepoints, stray symbols) that don't match a fixed bullet
# character list — without it, a document using an unrecognized bullet
# glyph silently falls through to one giant paragraph per section instead
# of one requirement per bullet. The trade-off: this can occasionally
# treat a stray punctuation mark as a bullet on prose text, producing an
# extra, slightly-too-short split — a much smaller problem than merging
# an entire policy section into a single unanalyzable blob.
_LIST_MARKER_RE = re.compile(
    r"^\s*(?:\(?\d{1,2}[.)]\s+|\(?[a-zA-Z][.)]\s+|[^\w\s]\s+)", re.MULTILINE
)

# Lines that look like running page headers/footers — "Page 3 of 6", or a
# short line (title/reference code) that repeats verbatim across the
# document. These get stripped before splitting so they never become
# their own fake "requirement." Detected structurally (by repetition),
# not by guessing specific header text, since header wording varies by
# document.
_PAGE_NUMBER_RE = re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
_BOILERPLATE_MAX_LINE_LENGTH = 120
_BOILERPLATE_MIN_REPEATS = 2


def _strip_boilerplate(text: str) -> str:
    """
    Removes running headers/footers before requirement splitting.
    A line counts as boilerplate if it matches a "Page X of Y" pattern,
    OR if it's short and appears verbatim more than once in the
    document (a repeated title/reference-code line printed on every
    page). Genuine requirement text is rarely both short AND repeated
    verbatim, so this is a safe structural signal rather than a guess
    at specific wording.
    """
    lines = text.split("\n")

    line_counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) <= _BOILERPLATE_MAX_LINE_LENGTH:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1

    kept_lines = []
    for line in lines:
        stripped = line.strip()
        if _PAGE_NUMBER_RE.search(stripped):
            continue
        if line_counts.get(stripped, 0) >= _BOILERPLATE_MIN_REPEATS:
            continue
        kept_lines.append(line)

    return "\n".join(kept_lines)


def split_into_requirements(text: str) -> list[str]:
    """
    Splits donor policy text into individual requirement-sized clauses.

    Strategy: strip repeated headers/footers first (see
    _strip_boilerplate), then, if the text contains numbered/bulleted
    list markers, split on those (donor policies are very commonly
    structured this way — "1. Grantees must...", "2. All programs
    shall..."). If no list structure is detected, fall back to
    splitting on blank-line paragraph breaks instead of returning the
    whole document as one giant "requirement."

    This is a heuristic, not a real document-structure parser — it
    will occasionally split a sentence oddly or merge two short related
    points. That's an acceptable trade-off for a v0 feature; the
    alternative (one clause per document) makes the feature useless.
    """
    text = _strip_boilerplate(text)
    marker_positions = [m.start() for m in _LIST_MARKER_RE.finditer(text)]

    if len(marker_positions) >= 2:
        chunks = []
        for i, start in enumerate(marker_positions):
            if i + 1 < len(marker_positions):
                end = marker_positions[i + 1]
            else:
                # Last detected list item: don't assume it runs to the
                # end of the document. A numbered list is very often
                # followed by unrelated prose (a different policy
                # section, a closing paragraph) — grabbing "everything
                # remaining" merges that unrelated content into the
                # final requirement, same failure mode as the
                # no-markers-found fallback this whole function exists
                # to avoid. Cap it at the first blank-line paragraph
                # break after the marker instead, so the last item is
                # sized like a normal requirement, not like a bucket
                # for the rest of the file.
                remainder = text[start:]
                boundary_match = re.search(r"\n\s*\n", remainder)
                end = start + boundary_match.start() if boundary_match else len(text)
            chunks.append(text[start:end].strip())
    else:
        chunks = [p.strip() for p in re.split(r"\n\s*\n", text)]

    return [c for c in chunks if len(c) >= MIN_REQUIREMENT_LENGTH]


def _build_summary(covered: int, partial: int, gap: int, total: int, truncated: bool) -> str:
    if total == 0:
        return "No requirements could be identified in the provided document or text."

    parts = [
        f"Analyzed {total} requirement{'s' if total != 1 else ''}: "
        f"{covered} covered, {partial} partially covered, {gap} gap{'s' if gap != 1 else ''}."
    ]
    if gap > 0:
        parts.append(
            f"{gap} requirement{'s' if gap != 1 else ''} appear to have no matching internal "
            "policy and should be reviewed."
        )
    if truncated:
        parts.append(
            f"Only the first {MAX_REQUIREMENTS} requirements were analyzed; "
            "the document contained more than this tool processes in one pass."
        )
    return " ".join(parts)


def analyze_gaps(
    db: Session, donor_text: str, requester_role: str
) -> GapAnalysisResult:
    all_requirements = split_into_requirements(donor_text)
    truncated = len(all_requirements) > MAX_REQUIREMENTS
    requirements = all_requirements[:MAX_REQUIREMENTS]

    items: list[GapItem] = []
    covered_count = partial_count = gap_count = 0

    for requirement in requirements:
        chunks = search_similar_chunks(
            db, requirement, top_k=CHUNKS_PER_REQUIREMENT, requester_role=requester_role
        )
        assessment = assess_requirement_coverage(requirement, chunks)

        if assessment.status == CoverageStatus.COVERED:
            covered_count += 1
        elif assessment.status == CoverageStatus.PARTIAL:
            partial_count += 1
        else:
            gap_count += 1

        items.append(
            GapItem(
                requirement=requirement,
                status=assessment.status,
                explanation=assessment.explanation,
                matched_documents=list({c.document_title for c in chunks}),
            )
        )

    summary = _build_summary(
        covered_count, partial_count, gap_count, len(requirements), truncated
    )

    return GapAnalysisResult(
        items=items,
        covered_count=covered_count,
        partial_count=partial_count,
        gap_count=gap_count,
        total_requirements=len(requirements),
        summary=summary,
        truncated=truncated,
    )