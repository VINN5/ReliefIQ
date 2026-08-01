"""
Shared prompt-injection detection, used at two points in the pipeline:

1. Ingestion time (chunking_service.chunk_pages) — the PRIMARY defense.
   Content is sanitized once, when a document is first chunked, so
   whatever gets stored in document_chunks is already clean.

2. Query time (generation_service._build_context_block) — a
   defense-in-depth SECOND pass, not the primary defense anymore. It
   still matters for two real cases: documents chunked before this
   module existed (their stored content was never sanitized at rest,
   only in-flight), and as a safety net against any future ingestion
   path that might bypass chunking_service.

Pattern-based, not NER/ML-based — this catches the common, blunt
injection attempts (a line telling the model to ignore its
instructions) without pretending to be a complete defense against a
sophisticated adversarial document. Living in one shared module
instead of two separate copies means the pattern list can only drift
out of sync with itself, not with a second, forgotten copy elsewhere.
"""

import logging
import re

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = [
    r"ignore (all|any|the)?\s*(previous|prior|above)\s*instructions",
    r"disregard (all|any|the)?\s*(previous|prior|above)\s*(instructions|text|prompt)",
    r"you are now\b",
    r"act as (a|an)\b",
    r"new instructions?\s*:",
    r"system\s*prompt\s*:",
    r"\bsystem\s*:\s*",
    r"reveal your (system )?prompt",
    r"forget (everything|all)? ?(you (were|have been) told|your instructions)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)
_REDACTION_MARKER = "[content removed by content filter]"


def strip_prompt_injection(text: str, *, source: str = "unknown") -> str:
    """
    Strips lines matching known prompt-injection patterns from `text`.
    Operates line-by-line rather than rejecting the whole text, since a
    document can be legitimate everywhere except one injected line —
    dropping everything would throw away real, useful content over one
    bad line.

    `source` is just for the log line (e.g. "ingestion" vs "query") so
    a hit can be traced back to which call site caught it.
    """
    lines = text.splitlines()
    cleaned_lines = []
    stripped_any = False
    for line in lines:
        if _INJECTION_RE.search(line):
            stripped_any = True
            cleaned_lines.append(_REDACTION_MARKER)
        else:
            cleaned_lines.append(line)

    if stripped_any:
        logger.warning("Stripped suspected prompt-injection content (source=%s)", source)

    return "\n".join(cleaned_lines)