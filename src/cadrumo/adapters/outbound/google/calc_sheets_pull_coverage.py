"""Coverage verification between a Sheets export plan and its pulled records."""

from __future__ import annotations

from ....application.storage.calc_sheets.records import SheetExportPlan
from .calc_sheets_pull_records import PullCoverageDiscrepancy, PullResult


def verify_pull_coverage(
    plan: SheetExportPlan,
    pull: PullResult,
) -> tuple[PullCoverageDiscrepancy, ...]:
    """Return every structural coverage discrepancy between ``plan`` and ``pull``."""
    discrepancies: list[PullCoverageDiscrepancy] = []

    plan_meta = plan.metadata
    pull_meta = pull.metadata
    for field_name in ("modelo_id", "revision_id", "filing_year", "period", "registry_sha"):
        plan_value = getattr(plan_meta, field_name)
        pull_value = getattr(pull_meta, field_name)
        if field_name == "period":
            plan_value = plan_meta.period.registry_token
        if pull_value != plan_value:
            discrepancies.append(
                PullCoverageDiscrepancy(
                    kind="metadata_mismatch",
                    detail=f"metadata field {field_name!r} differs between plan and pull",
                    expected=str(plan_value),
                    observed=str(pull_value),
                ),
            )

    planned_groupings = {row_set.grouping for row_set in plan.row_sets}
    pulled_groupings = {edit.grouping for edit in pull.row_set_edits}
    for missing in sorted(planned_groupings - pulled_groupings):
        discrepancies.append(
            PullCoverageDiscrepancy(
                kind="row_set_missing",
                detail=f"row-set grouping {missing!r} is declared by the plan but absent from the pull",
                expected=missing,
                observed="",
            ),
        )
    for extra in sorted(pulled_groupings - planned_groupings):
        discrepancies.append(
            PullCoverageDiscrepancy(
                kind="row_set_extra",
                detail=f"row-set grouping {extra!r} appears in the pull but is not declared by the plan",
                expected="",
                observed=extra,
            ),
        )

    return tuple(discrepancies)
