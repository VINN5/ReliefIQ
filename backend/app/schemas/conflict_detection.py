"""
Pydantic schemas for the conflict detection API.
"""

from pydantic import BaseModel


class ConflictItemResponse(BaseModel):
    target_excerpt: str
    target_page: int | None
    other_document_title: str
    other_excerpt: str
    other_page: int | None
    confidence: int
    explanation: str


class ConflictAnalysisResponse(BaseModel):
    document_title: str
    items: list[ConflictItemResponse]
    chunks_checked: int
    comparisons_made: int
    potential_conflicts_count: int
    truncated: bool
    summary: str