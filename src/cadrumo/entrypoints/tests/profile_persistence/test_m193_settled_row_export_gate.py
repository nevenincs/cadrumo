"""A Modelo 193 revision carrying a settled prior-accrual row is never written out as a fichero.

A key B coupon exigible in the last closed exercise and collected the next January
is a pending row of that exercise's Modelo 193 and a settled prior-accrual row of
the next one. No
official source settles the base and withholding the payment-year record
declares, so export refuses that collection-year revision from what it persisted. The
accrual-year revision carrying the pending row, and a collection-year revision of manual rows
only, pass the refusal. Real encrypted store, producer, calculation and export
services over the published authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_YEAR,
)
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.application.aggregation.m193_phase_materialization import (
    modelo_193_phase_rows_may_settle_prior_accruals,
)
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    published_pending_disclosure_years,
)
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.m193_settled_row_gate import Modelo193SettledRowAmountAuthorityUnresolvedError
from cadrumo.core.aggregation import (
    CalculationSourceLineageRole,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_supported_filing_years
from cadrumo.domain.modelos.calculation_revision import CalculationRevision

from ..m193_settled_row_support import (
    BUCKET_ID,
    M193Bucket,
    calculate_m193_revision,
    capture_coupon_collected_next_year,
    m193_bucket,
    persist_manual_row,
    stored_revision,
)
from ..modelo_gate_bucket_support import ready_workflow_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEAF = "modelo.export"


def _phase_contributors(revision: CalculationRevision) -> int:
    return sum(
        1
        for ref in revision.source_provenance
        if ref.resolver_id == WithholdingSourceResolver.resolver_id
        and ref.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
    )


def _export(
    bucket: M193Bucket,
    revision_id: CalculationRevisionId,
    output_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    export_modelo_revision(
        ModeloExportCommand(calculation_revision_id=revision_id, output_path=output_path, actor="test"),
        workflow_profile=ready_workflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=BUCKET_ID, secure_objects=bucket.objects),
        operation=operation,
    )


def _exported_events(bucket: M193Bucket) -> list[str]:
    catalogue = BucketEventHistoryRepository(objects=bucket.objects).load()
    return [
        event_id for event_id, event in catalogue.events.items() if event.event_type is BucketEventType.MODELO_EXPORTED
    ]


def test_a_settled_prior_accrual_row_refuses_export_and_writes_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The refusal is typed, has no command action, and leaves no fichero, event or state change."""
    export_path = tmp_path / f"modelo-193-{CAPITAL_YEAR + 1}-0A.txt"
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR + 1, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        assert _phase_contributors(revision) == 1

        with pytest.raises(Modelo193SettledRowAmountAuthorityUnresolvedError) as exc_info:
            _export(bucket, revision.calculation_revision_id, export_path, operation=operation)

        after = stored_revision(bucket, revision.calculation_revision_id)
        exported = _exported_events(bucket)

    error = exc_info.value
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == f"{_LEAF}.m193_settled_row_amount_authority.resolved"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert error.precondition_failure is not None
    assert error.precondition_failure.subject_leaf_key == _LEAF
    assert error.precondition_failure.scenario_id == f"{_LEAF}.m193_settled_row_amount_authority.unresolved"
    (condition_evidence,) = verdict.evidence
    assert condition_evidence.values["settled_prior_accrual_rows"] == 1
    assert condition_evidence.values["amount_authority_resolved"] is False
    assert condition_evidence.values["year"] == CAPITAL_YEAR + 1
    assert get_registered_error_code(error).code == "REFUSED_MODELO_193_SETTLED_ROW_AMOUNT_AUTHORITY_UNRESOLVED"
    assert not export_path.exists()
    assert list(tmp_path.glob(f"modelo-193-{CAPITAL_YEAR + 1}-0A*")) == []
    assert exported == []
    assert after == revision


def test_a_pending_row_in_its_accrual_year_is_not_refused_by_the_settled_row_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same coupon is a pending row in its accrual year, so export proceeds past the gate to its later checks."""
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        assert _phase_contributors(revision) == 1

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _export(
                bucket,
                revision.calculation_revision_id,
                tmp_path / f"modelo-193-{CAPITAL_YEAR}-0A.txt",
                operation=operation,
            )


def test_ordinary_rows_in_a_payment_year_are_not_refused_by_the_settled_row_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A collection-year revision of hand-declared rows carries no phase contributor, so the gate passes it."""
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR + 1, operation=operation) as bucket:
        persist_manual_row(bucket.objects, filing_year=CAPITAL_YEAR + 1)
        revision = calculate_m193_revision(bucket)
        assert _phase_contributors(revision) == 0

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _export(
                bucket,
                revision.calculation_revision_id,
                tmp_path / f"modelo-193-{CAPITAL_YEAR + 1}-0A.txt",
                operation=operation,
            )


def test_every_supported_modelo_193_edition_grounds_the_pending_disclosure() -> None:
    """Each record design the envelope selects prints the pending field for keys A, B and D."""
    support = published_supported_filing_years()
    assert support is not None
    assert published_pending_disclosure_years() == frozenset(support.years)


def test_only_a_year_after_a_grounded_accrual_year_can_hold_a_settled_row() -> None:
    """The phase materialisation's accrual-year bound is what tells a settled row from a pending one."""
    grounded = published_pending_disclosure_years()
    first = min(grounded)
    assert not modelo_193_phase_rows_may_settle_prior_accruals(first, pending_disclosure_years=grounded)
    for year in sorted(grounded - {first}):
        assert modelo_193_phase_rows_may_settle_prior_accruals(year, pending_disclosure_years=grounded)
