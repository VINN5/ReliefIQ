"""
Spreadsheet comparison service — compares two versions of the same
spreadsheet (linked via Document.supersedes_id, reusing the existing
versioning system) sheet by sheet.

Deliberately 100% deterministic — no LLM call anywhere in this module.
Every number in the result is computed directly from stored table data.
This matches the project's guardrail philosophy taken to its logical
conclusion: for a feature whose entire point is "tell me exactly what
changed in these numbers," letting a model narrate (and risk
paraphrasing/misstating) the diff would undermine the one thing this
tool needs to be trustworthy for.

Row matching strategy: rows are compared as whole units (by their full
content), not aligned by a guessed "key column" — there's no reliable
way to know which column is an identifier without the user telling us,
and guessing wrong silently produces a misleading diff. A row that's
identical in both versions doesn't appear in either "added" or
"removed" list; a row where even one cell changed appears as removed
(old values) and added (new values) — which is honest about what's
actually knowable without more information, rather than pretending to
detect "this specific cell changed" when that requires an assumption
this service doesn't make.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.spreadsheet_table import SpreadsheetTable

MAX_ROW_DIFFS_PER_SHEET = 50  # cap what's returned, not what's computed


@dataclass
class SheetComparison:
    sheet_name: str
    columns_added: list[str] = field(default_factory=list)
    columns_removed: list[str] = field(default_factory=list)
    rows_added: list[list] = field(default_factory=list)
    rows_removed: list[list] = field(default_factory=list)
    old_row_count: int = 0
    new_row_count: int = 0
    headers: list[str] = field(default_factory=list)
    truncated: bool = False


@dataclass
class SpreadsheetComparisonResult:
    old_document_title: str
    new_document_title: str
    sheets_added: list[str] = field(default_factory=list)
    sheets_removed: list[str] = field(default_factory=list)
    sheet_comparisons: list[SheetComparison] = field(default_factory=list)
    summary: str = ""


def _diff_rows(old_rows: list[list], new_rows: list[list]) -> tuple[list[list], list[list]]:
    """
    Set-based whole-row diff. Rows are converted to tuples so they can
    be hashed/compared; duplicate identical rows are treated as
    multiple occurrences of the same row (using a count-aware
    approach) rather than collapsed, so "3 identical rows in old, 2 in
    new" correctly reports one row as removed, not silently ignored.
    """
    from collections import Counter

    old_counts = Counter(tuple(row) for row in old_rows)
    new_counts = Counter(tuple(row) for row in new_rows)

    removed = list((old_counts - new_counts).elements())
    added = list((new_counts - old_counts).elements())

    return [list(r) for r in removed], [list(r) for r in added]


def compare_spreadsheet_versions(db: Session, document_id) -> SpreadsheetComparisonResult:
    new_document = db.query(Document).filter(Document.id == document_id).first()
    if new_document is None:
        raise ValueError("Document not found.")
    if new_document.doc_type not in ("xlsx", "csv"):
        raise ValueError("This document isn't a spreadsheet.")
    if new_document.supersedes_id is None:
        raise ValueError(
            "This spreadsheet has no earlier version to compare against — "
            "it wasn't uploaded as a replacement of an existing document."
        )

    old_document = db.query(Document).filter(Document.id == new_document.supersedes_id).first()
    if old_document is None:
        raise ValueError("The earlier version this document replaced could not be found.")

    old_tables = {
        t.sheet_name: t
        for t in db.query(SpreadsheetTable).filter(SpreadsheetTable.document_id == old_document.id)
    }
    new_tables = {
        t.sheet_name: t
        for t in db.query(SpreadsheetTable).filter(SpreadsheetTable.document_id == new_document.id)
    }

    sheets_removed = sorted(set(old_tables) - set(new_tables))
    sheets_added = sorted(set(new_tables) - set(old_tables))
    common_sheets = sorted(set(old_tables) & set(new_tables))

    sheet_comparisons: list[SheetComparison] = []
    for sheet_name in common_sheets:
        old_table = old_tables[sheet_name]
        new_table = new_tables[sheet_name]

        rows_removed, rows_added = _diff_rows(old_table.rows, new_table.rows)
        truncated = len(rows_removed) > MAX_ROW_DIFFS_PER_SHEET or len(rows_added) > MAX_ROW_DIFFS_PER_SHEET

        sheet_comparisons.append(
            SheetComparison(
                sheet_name=sheet_name,
                columns_added=[h for h in new_table.headers if h not in old_table.headers],
                columns_removed=[h for h in old_table.headers if h not in new_table.headers],
                rows_added=rows_added[:MAX_ROW_DIFFS_PER_SHEET],
                rows_removed=rows_removed[:MAX_ROW_DIFFS_PER_SHEET],
                old_row_count=old_table.row_count,
                new_row_count=new_table.row_count,
                headers=new_table.headers,
                truncated=truncated,
            )
        )

    summary = _build_summary(new_document.title, sheets_added, sheets_removed, sheet_comparisons)

    return SpreadsheetComparisonResult(
        old_document_title=old_document.title,
        new_document_title=new_document.title,
        sheets_added=sheets_added,
        sheets_removed=sheets_removed,
        sheet_comparisons=sheet_comparisons,
        summary=summary,
    )


def _build_summary(
    title: str, sheets_added: list[str], sheets_removed: list[str], comparisons: list[SheetComparison]
) -> str:
    parts = [f"Comparing '{title}' against the version it replaced."]

    if sheets_added:
        parts.append(f"{len(sheets_added)} new sheet(s): {', '.join(sheets_added)}.")
    if sheets_removed:
        parts.append(f"{len(sheets_removed)} sheet(s) removed: {', '.join(sheets_removed)}.")

    total_added = sum(len(c.rows_added) for c in comparisons)
    total_removed = sum(len(c.rows_removed) for c in comparisons)
    if total_added or total_removed:
        parts.append(
            f"Across {len(comparisons)} shared sheet(s): {total_added} row(s) added, "
            f"{total_removed} row(s) removed or changed."
        )
    elif comparisons:
        parts.append(f"No row-level changes found across {len(comparisons)} shared sheet(s).")

    return " ".join(parts)