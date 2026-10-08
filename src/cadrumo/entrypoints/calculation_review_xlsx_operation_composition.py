"""Bind selected-revision custody to the canonical offline workbook materializer."""

from __future__ import annotations

from uuid import UUID

from ..application.export.calculation_review_xlsx_operation import CalculationReviewXlsxPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .calculation_review_snapshot_composition import load_calculation_review_snapshot


def build_calculation_review_xlsx_ports(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
) -> CalculationReviewXlsxPorts:
    """Prepare local-only ports; no provider configuration, login or network access."""
    from ..adapters.outbound.workbook.calc_sheets_xlsx import materialize_export_plan

    return CalculationReviewXlsxPorts(
        profile_id=profile_id,
        operation=operation,
        load_snapshot=lambda revision_id, filing_record_id: load_calculation_review_snapshot(
            revision_id,
            profile_id=profile_id,
            operation=operation,
            filing_record_id=filing_record_id,
        ),
        materialize=materialize_export_plan,
    )
