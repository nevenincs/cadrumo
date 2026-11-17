"""What the last check found about the values of each section's tables of records.

A finding about a value every record of a table carries names a record column,
not a box the filer can open, so it stands for the section that holds the
table: a section is not done while one of its tables misses a value. Each
level is counted as the header counts it: an explanation counts nowhere, and a
declaration recorded as filed asks nothing more. A section on a page that does
not apply asks for no value, so only what is worth checking counts there.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from .work_form_findings import ModeloFormAttention, ModeloFormIssue
from .work_form_models import (
    ModeloFormPage,
    ModeloFormRecordAttention,
    ModeloFormRepeatingBlock,
    ModeloFormSection,
)

__all__ = ["record_attention", "with_record_attention"]

_COUNTED_LEVELS: Final[tuple[ModeloFormAttention, ...]] = (
    ModeloFormAttention.BLOCKS,
    ModeloFormAttention.MISSING,
    ModeloFormAttention.CONFIRM,
    ModeloFormAttention.CHECK,
    ModeloFormAttention.LIMITATION,
)
"""The levels a section counts, most urgent first, as the header counts them."""
_UNASKED_LEVELS: Final[frozenset[ModeloFormAttention]] = frozenset(
    {ModeloFormAttention.CHECK, ModeloFormAttention.LIMITATION}
)
"""The levels still worth counting where nothing is asked of the filer."""


def _record_columns(section: ModeloFormSection) -> frozenset[str]:
    return frozenset(
        str(casilla_id)
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
        for casilla_id in block.column_casilla_ids
        if casilla_id is not None
    )


def record_attention(
    section: ModeloFormSection, issues: tuple[ModeloFormIssue, ...], *, recorded: bool, applies: bool
) -> tuple[ModeloFormRecordAttention, ...]:
    """One count per level with any finding about ``section``'s record columns, most urgent first."""
    columns = _record_columns(section)
    if recorded or not columns:
        return ()
    counted = Counter(
        issue.attention
        for issue in issues
        if issue.finding.casilla_id is not None
        and str(issue.finding.casilla_id) in columns
        and (applies or issue.attention in _UNASKED_LEVELS)
    )
    return tuple(
        ModeloFormRecordAttention.counted(level, counted[level]) for level in _COUNTED_LEVELS if counted[level]
    )


def with_record_attention(
    pages: tuple[ModeloFormPage, ...], issues: tuple[ModeloFormIssue, ...], *, recorded: bool
) -> tuple[ModeloFormPage, ...]:
    """``pages`` with each section's record attention, as the last check's ``issues`` decide it."""
    if not issues:
        return pages
    return tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "record_attention": record_attention(
                                section, issues, recorded=recorded, applies=page.applies is not False
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in pages
    )
