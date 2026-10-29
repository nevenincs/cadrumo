"""Render calculation identity and lifecycle facts on a review overview."""

from __future__ import annotations

from collections.abc import Callable

from ...export.review_snapshot import CalculationReviewSelection, ReviewCalculationLifecycle, ReviewSnapshot
from .workbook_cells import SheetCellValue

type ReviewLabelResolver = Callable[[str], str]


def append_calculation_overview(
    overview: list[tuple[SheetCellValue, ...]],
    snapshot: ReviewSnapshot,
    selection: CalculationReviewSelection,
    label: ReviewLabelResolver,
) -> None:
    """Append captured lifecycle and calculation coordinates in order."""
    lifecycle = snapshot.calculation_lifecycle
    overview.extend(
        (
            (
                label("calculation_state"),
                _calculation_state(lifecycle, label),
            ),
            (
                label("current_calculation"),
                _lifecycle_flag(lifecycle.is_current_calculation if lifecycle else None, label),
            ),
            (
                label("current_filing"),
                _lifecycle_flag(lifecycle.is_current_filing if lifecycle else None, label),
            ),
            (
                label("aeat_confirmation"),
                label("aeat_confirmation_" + lifecycle.aeat_confirmation.value)
                if lifecycle and (lifecycle.aeat_confirmation is not None and lifecycle.aeat_confirmation)
                else label("not_captured"),
            ),
            (
                label("filing_status"),
                label("filing_status_" + lifecycle.filing_status.value)
                if lifecycle and (lifecycle.filing_status is not None and lifecycle.filing_status)
                else label("not_captured"),
            ),
            (label("filing_record"), lifecycle.filing_record_id if lifecycle else None),
        )
    )
    overview.extend(
        (
            (label("modelo"), selection.modelo),
            (label("period"), f"{selection.filing_year} / {selection.period}"),
            (label("work_unit"), selection.work_unit_id),
            (label("calculation_revision"), selection.calculation_revision_id),
            (label("registry_revision"), selection.registry_snapshot_ref.revision_id),
            (label("authority"), selection.authority_generation),
            (label("registry_digest"), selection.registry_digest),
        )
    )


def _lifecycle_flag(value: bool | None, label: ReviewLabelResolver) -> str:
    if value is None:
        return label("not_captured")
    return label("yes") if value else label("no")


def _calculation_state(lifecycle: ReviewCalculationLifecycle | None, label: ReviewLabelResolver) -> str:
    return label("calculation_state_" + lifecycle.state.value) if lifecycle else label("not_captured")
