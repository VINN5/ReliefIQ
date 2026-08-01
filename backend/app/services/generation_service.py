"""
Generation service — turns retrieved chunks into a grounded, cited
answer using an LLM. This is the anti-hallucination core of the
system: the model is instructed to answer ONLY from the provided
context, cite which source each claim comes from, and say so
explicitly when the context doesn't contain an answer, rather than
falling back on its own general knowledge.

Two server-side guardrails live here, deliberately not left to prompt
instructions alone (a system prompt is a request, not an enforcement
mechanism — the model can be wrong or manipulated):

1. Citation enforcement: if chunks were provided but the model's
   answer contains no citation markers at all, the raw answer is
   discarded and replaced with a safe fallback.

2. Prompt-injection stripping: retrieved chunk content is scanned for
   common injection patterns before being placed in the context block.

Supports multiple LLM providers (Gemini, OpenAI, Anthropic, Groq) with
an ordered fallback chain via _call_with_fallback(), shared by
generate_answer() (Q&A), assess_requirement_coverage() (gap
detection), and assess_conflict() (conflict detection) — one
fallback/cooldown implementation, three different system instructions
on top of it.
"""

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from app.services.content_safety import strip_prompt_injection
from app.services.retrieval_service import RetrievedChunk

logger = logging.getLogger(__name__)

_QA_SYSTEM_INSTRUCTION = """You are a knowledge assistant for NGO staff. You answer questions \
using ONLY the numbered source excerpts provided below — never your own general knowledge, \
even if you believe you know the answer.

Rules:
- Every factual claim in your answer must be traceable to one of the numbered sources.
- Cite sources inline using their number in square brackets, e.g. [1], immediately after \
the claim it supports.
- If the sources do not contain enough information to answer the question, say so \
explicitly and do not guess or fill gaps with outside knowledge.
- Be concise and direct. Do not repeat the question back or add unnecessary preamble."""

_UNCITED_FALLBACK_TEXT = (
    "I found some potentially related information, but couldn't produce an answer "
    "with verified citations for this question. Please consult the source documents "
    "directly, or reach out to your program manager."
)


class Provider(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"


@dataclass
class GeneratedAnswer:
    answer_text: str
    provider_used: str | None = None
    grounding_rejected: bool = False


# ---------------------------------------------------------------------------
# Prompt-injection stripping — see content_safety.py's module docstring
# for the full rationale. This is now a SECOND, defense-in-depth pass:
# the primary stripping happens at ingestion time in chunking_service.py,
# so content pulled from document_chunks should already be clean. This
# call still matters for documents chunked before that existed, and as
# a safety net if some future path bypasses chunking_service.
# ---------------------------------------------------------------------------

_CITATION_MARKER_RE = re.compile(r"\[\d+\]")


def _has_citations(answer_text: str) -> bool:
    return bool(_CITATION_MARKER_RE.search(answer_text))


# ---------------------------------------------------------------------------
# Lazy-singleton clients
# ---------------------------------------------------------------------------

_gemini_client = None
_openai_client = None
_anthropic_client = None
_groq_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic

        _anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Per-provider call functions — each takes (system_instruction, user_prompt)
# and returns raw text. Any exception propagates so the fallback loop can
# try the next provider.
# ---------------------------------------------------------------------------


def _call_gemini(system_instruction: str, prompt: str) -> str:
    from google.genai import types

    response = _get_gemini_client().models.generate_content(
        model=settings.generation_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
        ),
    )
    return response.text


def _call_openai(system_instruction: str, prompt: str) -> str:
    response = _get_openai_client().chat.completions.create(
        model=settings.openai_generation_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def _call_anthropic(system_instruction: str, prompt: str) -> str:
    response = _get_anthropic_client().messages.create(
        model=settings.anthropic_generation_model,
        max_tokens=1024,
        temperature=0.2,
        system=system_instruction,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_groq(system_instruction: str, prompt: str) -> str:
    response = _get_groq_client().chat.completions.create(
        model=settings.groq_generation_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


_PROVIDER_FUNCS = {
    Provider.GEMINI: _call_gemini,
    Provider.OPENAI: _call_openai,
    Provider.ANTHROPIC: _call_anthropic,
    Provider.GROQ: _call_groq,
}


# ---------------------------------------------------------------------------
# Cooldown / circuit-breaker state — shared across every call site, since
# a provider that's down for Q&A is equally down for gap detection.
# ---------------------------------------------------------------------------

_COOLDOWN_SECONDS = 300
_provider_failed_at: dict[str, float] = {}


def _is_in_cooldown(provider_name: str) -> bool:
    failed_at = _provider_failed_at.get(provider_name)
    if failed_at is None:
        return False
    return (time.monotonic() - failed_at) < _COOLDOWN_SECONDS


def _mark_failed(provider_name: str) -> None:
    _provider_failed_at[provider_name] = time.monotonic()


def _mark_recovered(provider_name: str) -> None:
    _provider_failed_at.pop(provider_name, None)


def _call_with_fallback(system_instruction: str, prompt: str) -> tuple[str, str]:
    """
    Shared fallback/cooldown loop. Returns (raw_text, provider_value).
    Raises RuntimeError if every provider fails. This is the one place
    that knows about provider order, cooldown, and retry-after-cooldown
    — generate_answer() and assess_requirement_coverage() both call
    this instead of each maintaining their own copy of the loop.
    """
    provider_order = [settings.generation_provider] + [
        p for p in settings.fallback_providers if p != settings.generation_provider
    ]

    last_error: Exception | None = None
    skipped_in_cooldown: list[str] = []

    for provider_name in provider_order:
        try:
            provider = Provider(provider_name)
        except ValueError:
            logger.warning("Unknown generation provider '%s', skipping", provider_name)
            continue

        if _is_in_cooldown(provider.value):
            skipped_in_cooldown.append(provider.value)
            continue

        try:
            text = _PROVIDER_FUNCS[provider](system_instruction, prompt)
            _mark_recovered(provider.value)
            return text, provider.value
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any provider failure should fall through
            logger.warning("Generation provider '%s' failed: %s", provider.value, exc)
            _mark_failed(provider.value)
            last_error = exc
            continue

    if last_error is None and skipped_in_cooldown:
        forced_provider = Provider(provider_order[0])
        try:
            text = _PROVIDER_FUNCS[forced_provider](system_instruction, prompt)
            _mark_recovered(forced_provider.value)
            return text, forced_provider.value
        except Exception as exc:  # noqa: BLE001
            _mark_failed(forced_provider.value)
            last_error = exc

    raise RuntimeError(
        f"All generation providers failed (tried: {provider_order}, "
        f"in cooldown: {skipped_in_cooldown}). Last error: {last_error}"
    ) from last_error


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    sources = []
    for i, chunk in enumerate(chunks, start=1):
        page_info = f", page {chunk.page_number}" if chunk.page_number else ""
        safe_content = strip_prompt_injection(chunk.content, source="query")
        sources.append(
            f"[{i}] Source: {chunk.document_title}{page_info}\n{safe_content}"
        )
    return "\n\n".join(sources)


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
    """
    Given a question and its retrieved chunks, asks an LLM to produce a
    grounded, cited answer. If `chunks` is empty, skips the API call
    entirely and returns a fixed "no information found" response.
    """
    if not chunks:
        return GeneratedAnswer(
            answer_text="I couldn't find any relevant information in the available documents to answer this question."
        )

    context_block = _build_context_block(chunks)
    prompt = f"Sources:\n\n{context_block}\n\nQuestion: {question}"

    try:
        answer_text, provider_value = _call_with_fallback(_QA_SYSTEM_INSTRUCTION, prompt)
    except RuntimeError:
        raise

    if not _has_citations(answer_text):
        logger.warning(
            "Provider '%s' returned an answer with no citation markers; "
            "rejecting and returning the safe fallback instead",
            provider_value,
        )
        return GeneratedAnswer(
            answer_text=_UNCITED_FALLBACK_TEXT,
            provider_used=provider_value,
            grounding_rejected=True,
        )

    return GeneratedAnswer(answer_text=answer_text, provider_used=provider_value)


# ---------------------------------------------------------------------------
# Gap detection — classifies whether a single donor requirement is covered
# by the organisation's own internal policies, based on retrieved chunks.
# ---------------------------------------------------------------------------

_GAP_SYSTEM_INSTRUCTION = """You are a compliance analyst for an NGO. You are given ONE \
requirement from a donor's policy document, and a set of numbered excerpts from the \
organisation's OWN internal policies that were retrieved as potentially related.

Decide whether the organisation's internal policies actually cover this requirement.

Respond in EXACTLY this format, with no extra commentary:
STATUS: <one of COVERED, PARTIAL, GAP>
EXPLANATION: <one or two sentences, citing source numbers like [1] where relevant>

Guidance:
- COVERED: the excerpts clearly and directly address the requirement.
- PARTIAL: the excerpts are related but don't fully address the requirement, or only \
address part of it.
- GAP: the excerpts don't meaningfully address the requirement at all, or no excerpts \
were provided.
- Do not guess or assume policies exist beyond what's shown in the excerpts."""


class CoverageStatus(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"


@dataclass
class RequirementAssessment:
    status: CoverageStatus
    explanation: str
    provider_used: str | None = None


_STATUS_LINE_RE = re.compile(r"STATUS:\s*(COVERED|PARTIAL|GAP)", re.IGNORECASE)
_EXPLANATION_LINE_RE = re.compile(r"EXPLANATION:\s*(.+)", re.IGNORECASE | re.DOTALL)

_STATUS_MAP = {
    "COVERED": CoverageStatus.COVERED,
    "PARTIAL": CoverageStatus.PARTIAL,
    "GAP": CoverageStatus.GAP,
}


def assess_requirement_coverage(
    requirement: str, chunks: list[RetrievedChunk]
) -> RequirementAssessment:
    """
    Classifies a single donor requirement as COVERED / PARTIAL / GAP
    against the given (already-retrieved, already-RBAC-filtered) internal
    policy chunks. No chunks at all is treated as an automatic GAP
    without calling the LLM — there's nothing to assess against, same
    philosophy as generate_answer()'s empty-chunks short-circuit.
    """
    if not chunks:
        return RequirementAssessment(
            status=CoverageStatus.GAP,
            explanation="No related internal policy content was found for this requirement.",
        )

    context_block = _build_context_block(chunks)
    prompt = (
        f"Donor requirement:\n{requirement}\n\n"
        f"Internal policy excerpts:\n\n{context_block}"
    )

    try:
        raw_text, provider_value = _call_with_fallback(_GAP_SYSTEM_INSTRUCTION, prompt)
    except RuntimeError:
        raise

    status_match = _STATUS_LINE_RE.search(raw_text)
    explanation_match = _EXPLANATION_LINE_RE.search(raw_text)

    if not status_match:
        # Model didn't follow the format — fail safe rather than guess.
        # A misparsed "COVERED" would hide a real gap from a compliance
        # reviewer; a misparsed "GAP" just causes an extra manual check.
        logger.warning(
            "Provider '%s' returned an unparsable gap assessment: %r", provider_value, raw_text
        )
        return RequirementAssessment(
            status=CoverageStatus.GAP,
            explanation="Could not automatically assess this requirement — please review manually.",
            provider_used=provider_value,
        )

    status = _STATUS_MAP[status_match.group(1).upper()]
    explanation = explanation_match.group(1).strip() if explanation_match else raw_text.strip()

    return RequirementAssessment(status=status, explanation=explanation, provider_used=provider_value)


# ---------------------------------------------------------------------------
# Conflict detection — classifies whether two excerpts from DIFFERENT
# internal documents contain contradicting guidance. Unlike gap detection
# (donor requirement vs. internal policy), this is internal-vs-internal:
# both excerpts come from the org's own knowledge base.
# ---------------------------------------------------------------------------

_CONFLICT_SYSTEM_INSTRUCTION = """You are a policy compliance analyst for an NGO. You are \
given two excerpts from DIFFERENT internal policy documents. They were retrieved because \
they are topically related — your job is to determine whether they give CONTRADICTORY or \
INCONSISTENT guidance to staff, not merely whether they cover the same topic.

Respond in EXACTLY this format, with no extra commentary:
STATUS: <one of NO_CONFLICT, POTENTIAL_CONFLICT>
CONFIDENCE: <integer 0-100>
EXPLANATION: <one or two sentences explaining the reasoning>

Guidance:
- POTENTIAL_CONFLICT: the excerpts would give a staff member genuinely different or \
incompatible instructions in the same situation (e.g. one permits something the other \
prohibits, or they specify different numeric thresholds/timeframes for the same rule).
- NO_CONFLICT: the excerpts are consistent, cover different scenarios, or one is simply \
more specific/detailed than the other without contradicting it.
- Confidence reflects how clear-cut the conflict is, not how similar the topics are —
  two excerpts on the same topic that don't actually conflict should be NO_CONFLICT
  regardless of how related they seem.
- Do not flag a conflict just because two documents phrase the same rule differently."""


class ConflictStatus(str, Enum):
    NO_CONFLICT = "no_conflict"
    POTENTIAL_CONFLICT = "potential_conflict"


@dataclass
class ConflictAssessment:
    status: ConflictStatus
    confidence: int
    explanation: str
    provider_used: str | None = None


_CONFLICT_STATUS_LINE_RE = re.compile(r"STATUS:\s*(NO_CONFLICT|POTENTIAL_CONFLICT)", re.IGNORECASE)
_CONFLICT_CONFIDENCE_LINE_RE = re.compile(r"CONFIDENCE:\s*(\d{1,3})")
_CONFLICT_EXPLANATION_LINE_RE = re.compile(r"EXPLANATION:\s*(.+)", re.IGNORECASE | re.DOTALL)

_CONFLICT_STATUS_MAP = {
    "NO_CONFLICT": ConflictStatus.NO_CONFLICT,
    "POTENTIAL_CONFLICT": ConflictStatus.POTENTIAL_CONFLICT,
}


def assess_conflict(
    excerpt_a: str, title_a: str, excerpt_b: str, title_b: str
) -> ConflictAssessment:
    """
    Classifies whether two excerpts from different documents conflict.
    Both excerpts are passed through strip_prompt_injection() before
    reaching the prompt — same defense-in-depth reasoning as
    _build_context_block(), since this content comes from the same
    document_chunks table (already sanitized at ingestion, but this is
    a second-layer safety net regardless).
    """
    safe_a = strip_prompt_injection(excerpt_a, source="conflict_detection")
    safe_b = strip_prompt_injection(excerpt_b, source="conflict_detection")

    prompt = (
        f"Excerpt A — from \"{title_a}\":\n{safe_a}\n\n"
        f"Excerpt B — from \"{title_b}\":\n{safe_b}"
    )

    raw_text, provider_value = _call_with_fallback(_CONFLICT_SYSTEM_INSTRUCTION, prompt)

    status_match = _CONFLICT_STATUS_LINE_RE.search(raw_text)
    confidence_match = _CONFLICT_CONFIDENCE_LINE_RE.search(raw_text)
    explanation_match = _CONFLICT_EXPLANATION_LINE_RE.search(raw_text)

    if not status_match:
        # Fail safe: an unparsable response is treated as NO_CONFLICT
        # with 0 confidence rather than guessed as a conflict — a
        # false "no conflict" here just means one fewer flagged pair
        # for a human to review manually; a false "conflict" would
        # bury real findings in noise and erode trust in the feature.
        logger.warning(
            "Provider '%s' returned an unparsable conflict assessment: %r", provider_value, raw_text
        )
        return ConflictAssessment(
            status=ConflictStatus.NO_CONFLICT,
            confidence=0,
            explanation="Could not automatically assess this pair — skipped.",
            provider_used=provider_value,
        )

    status = _CONFLICT_STATUS_MAP[status_match.group(1).upper()]
    confidence = int(confidence_match.group(1)) if confidence_match else 0
    confidence = max(0, min(100, confidence))
    explanation = explanation_match.group(1).strip() if explanation_match else raw_text.strip()

    return ConflictAssessment(
        status=status, confidence=confidence, explanation=explanation, provider_used=provider_value
    )