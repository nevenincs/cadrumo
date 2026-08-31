"""Tests for the opt-in pull-coverage validator.

``verify_pull_coverage`` is the caller-facing helper that detects
structural mismatches between the ``SheetExportPlan`` an apply pass
wrote and the ``PullResult`` a subsequent pull pass produced.
Without it, a corrupted or hand-edited workbook could have row-sets
removed or metadata flipped without surfacing as a load error.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from .....application.storage.calc_sheets import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetRowSet,
    SheetRowSetColumn,
    TabName,
)
from .....core import Period
from ..calc_sheets_pull import (
    MetadataMatchState,
    PullCoverageDiscrepancy,
    PullMetadata,
    PullResult,
    RowSetCellEdit,
    RowSetEdit,
    verify_pull_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TEST_LEGAL_REFS = ("ley-58-2003:art-119",)
_TEST_SOURCE_REFS = ("aeat-dr-190-2025",)


def _plan_metadata() -> SheetExportMetadata:
    return SheetExportMetadata(
        modelo_id="100",
        revision_id="2024-y-siguientes",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        engine_version="v1.2.3",
        registry_sha="0123456789abcdef" * 4,
        exported_at=datetime(2025, 4, 15, 10, 30, 0, tzinfo=UTC),
    )


def _pull_metadata_matching(plan_meta: SheetExportMetadata) -> PullMetadata:
    return PullMetadata(
        modelo_id=plan_meta.modelo_id,
        revision_id=plan_meta.revision_id,
        filing_year=plan_meta.filing_year,
        period=plan_meta.period.registry_token,
        engine_version=plan_meta.engine_version,
        registry_sha=plan_meta.registry_sha,
        exported_at=plan_meta.exported_at.isoformat(),
    )


def _populated_plan(*, row_set_groupings: tuple[str, ...] = ("detalle-actividades",)) -> SheetExportPlan:
    metadata = _plan_metadata()
    row_sets = tuple(
        SheetRowSet(
            grouping=grouping,
            tab=TabName.DETALLE,
            header_row=1,
            first_data_row=2,
            columns=(
                SheetRowSetColumn(
                    binding=f"binding.{grouping}.code",
                    header_address=SheetCellAddress(tab=TabName.DETALLE, row=1, column=1, a1="A1"),
                    header_label="Código",
                    legal_refs=_TEST_LEGAL_REFS,
                ),
            ),
            legal_refs=_TEST_LEGAL_REFS,
            source_refs=_TEST_SOURCE_REFS,
        )
        for grouping in row_set_groupings
    )
    return SheetExportPlan(
        metadata=metadata,
        row_sets=row_sets,
        guide=SheetGuideContent(title="Guide", paragraphs=("Test guide.",)),
    )


def _populated_pull(
    plan: SheetExportPlan,
    *,
    row_set_groupings: tuple[str, ...] | None = None,
    metadata_overrides: dict[str, object] | None = None,
) -> PullResult:
    pull_meta = _pull_metadata_matching(plan.metadata)
    if metadata_overrides:
        pull_meta = pull_meta.model_copy(update=metadata_overrides)
    groupings = row_set_groupings if row_set_groupings is not None else tuple(rs.grouping for rs in plan.row_sets)
    return PullResult(
        spreadsheet_id="sheet-id",
        operator_edits=(),
        binding_edits=(),
        relation_edits=(),
        row_set_edits=tuple(
            RowSetEdit(
                grouping=grouping,
                cells=(RowSetCellEdit(binding=f"binding.{grouping}.code", row_index=1, value="row-1"),),
            )
            for grouping in groupings
        ),
        metadata=pull_meta,
        metadata_match=MetadataMatchState.MATCHES,
        cells_read=1,
    )


def test_verify_pull_coverage_matching_plan_returns_empty() -> None:
    """Plan and pull that agree on metadata + row-sets produce no discrepancies."""

    plan = _populated_plan()
    pull = _populated_pull(plan)
    assert verify_pull_coverage(plan, pull) == ()


def test_verify_pull_coverage_detects_metadata_drift() -> None:
    """A pull whose revision_id has shifted surfaces as a metadata_mismatch."""

    plan = _populated_plan()
    pull = _populated_pull(plan, metadata_overrides={"revision_id": "2023-y-siguientes"})
    discrepancies = verify_pull_coverage(plan, pull)
    assert any(d.kind == "metadata_mismatch" and "revision_id" in d.detail for d in discrepancies)
    flagged = next(d for d in discrepancies if d.kind == "metadata_mismatch")
    assert flagged.expected == "2024-y-siguientes"
    assert flagged.observed == "2023-y-siguientes"


def test_verify_pull_coverage_detects_registry_sha_drift() -> None:
    """Matching modelo coordinates still fail coverage when registry SHA drifts."""

    plan = _populated_plan()
    pull = _populated_pull(plan, metadata_overrides={"registry_sha": "deadbeef" * 8})
    discrepancies = verify_pull_coverage(plan, pull)
    flagged = next(d for d in discrepancies if d.kind == "metadata_mismatch" and "registry_sha" in d.detail)
    assert flagged.expected == plan.metadata.registry_sha
    assert flagged.observed == "deadbeef" * 8


def test_verify_pull_coverage_detects_missing_row_set() -> None:
    """A row-set declared by the plan but absent from the pull surfaces explicitly."""

    plan = _populated_plan(row_set_groupings=("detalle-actividades", "detalle-perceptors"))
    pull = _populated_pull(plan, row_set_groupings=("detalle-actividades",))
    discrepancies = verify_pull_coverage(plan, pull)
    assert any(d.kind == "row_set_missing" and d.expected == "detalle-perceptors" for d in discrepancies)


def test_verify_pull_coverage_detects_extra_row_set() -> None:
    """A row-set in the pull that the plan never declared surfaces as extra."""

    plan = _populated_plan(row_set_groupings=("detalle-actividades",))
    pull = _populated_pull(plan, row_set_groupings=("detalle-actividades", "detalle-rogue"))
    discrepancies = verify_pull_coverage(plan, pull)
    assert any(d.kind == "row_set_extra" and d.observed == "detalle-rogue" for d in discrepancies)


def test_pull_coverage_discrepancy_model_is_strict_frozen_forbid_extras() -> None:
    """The discrepancy record itself follows the boundary-record mandate."""

    PullCoverageDiscrepancy(
        kind="metadata_mismatch",
        detail="something",
        expected="x",
        observed="y",
    )
    with pytest.raises(ValidationError):
        PullCoverageDiscrepancy.model_validate(
            {
                "kind": "metadata_mismatch",
                "detail": "x",
                "extra_unknown_key": "boom",
            },
        )
