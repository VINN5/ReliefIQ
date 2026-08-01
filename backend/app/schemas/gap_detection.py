"""
Pydantic schemas for the gap detection API.
"""

import enum

from pydantic import BaseModel


class CoverageStatus(str, enum.Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"


class GapItemResponse(BaseModel):
    requirement: str
    status: CoverageStatus
    explanation: str
    matched_documents: list[str]


class GapAnalysisResponse(BaseModel):
    items: list[GapItemResponse]
    covered_count: int
    partial_count: int
    gap_count: int
    total_requirements: int
    summary: str
    truncated: bool