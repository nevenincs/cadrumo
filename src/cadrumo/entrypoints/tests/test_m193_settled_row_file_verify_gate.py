"""A Modelo 193 settled prior-accrual row is refused at local filing and reported at verification.

A key B coupon exigible in the last closed exercise and collected the next January
is a pending row of that exercise's Modelo 193 and a settled prior-accrual row of
the next one. Local filing refuses the collection-year revision with the export gate's typed reason, and
verification reports the same detection as a non-blocking finding. The
revision persists the contributor's accrual year, so the gates tell a settled
row from a pending one exactly; a revision persisted without it falls back to
the conservative filing-year rule. Real encrypted store, producer, calculation,
verification and filing services over the published authority.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    CAPITAL_YEAR,
)
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.m193_settled_row_gate import (
    Modelo193SettledRowAmountAuthorityUnresolvedError,
    modelo_193_settled_prior_accrual_contributors,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.core.aggregation import (
    CalculationSourceLineageRole,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.calculation_revision_sources import CalculationSourceRef
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import build_filing_action_ports
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from .m193_settled_row_support import (
    BUCKET_ID,
    M193Bucket,
    calculate_m193_revision,
    capture_coupon_collected_next_year,
    m193_bucket,
    persist_manual_row,
    stored_revision,
)
from .modelo_gate_bucket_support import ready_workflow_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_FILE_LEAF = "modelo.work.file"
_FINDING_KEY = "application.modelo.findings.m193_settled_row_amount_authority_unresolved"


def _stored_work_unit(bucket: M193Bucket) -> WorkUnit:
    work_unit = WorkUnitCatalogueRepository(objects=bucket.objects).load().get(bucket.work_unit_id)
    assert work_unit is not None
    return work_unit


def _phase_contributors(revision: CalculationRevision) -> tuple[CalculationSourceRef, ...]:
    return tuple(
        ref
        for ref in revision.source_provenance
        if ref.resolver_id == WithholdingSourceResolver.resolver_id
        and ref.lineage_role is CalculationSourceLineageRole.CONTRIBUTOR
    )


def _verify(revision_id: CalculationRevisionId, *, operation: PinnedAuthorityOperation) -> VerificationReport:
    return verify_modelo_revision_with_preconditions(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        actor="test",
        workflow_profile=ready_workflow_profile(),
        verification_repositories=build_test_verification_repository_bundle(),
        operation=operation,
    ).report


def _file(revision_id: CalculationRevisionId, *, operation: PinnedAuthorityOperation) -> None:
    # These cases assert an earlier settled-row/state refusal. No granting
    # verification report exists; the caller-supplied ID has no authority.
    file_modelo_revision(
        revision_id,
        approved_verification_report_id="0" * 64,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        ports=build_filing_action_ports(bucket_id=BUCKET_ID, operation=operation),
        actor="test",
        workflow_profile=ready_workflow_profile(),
        operation=operation,
    )


def _settled_row_findings(report: VerificationReport) -> list[ModeloVerificationFinding]:
    return [finding for finding in report.findings if finding.message_locale_key == _FINDING_KEY]


def _filed_events(bucket: M193Bucket) -> list[str]:
    catalogue = BucketEventHistoryRepository(objects=bucket.objects).load()
    return [
        event_id for event_id, event in catalogue.events.items() if event.event_type is BucketEventType.MODELO_FILED
    ]


def _with_source_filing_years(revision: CalculationRevision, year: int | None) -> CalculationRevision:
    """Rebuild ``revision`` with every phase contributor's accrual year set to ``year``, under its derived id."""
    provenance = tuple(
        ref.model_copy(update={"source_filing_year": year}) if ref in _phase_contributors(revision) else ref
        for ref in revision.source_provenance
    )
    rebuilt = revision.model_copy(update={"source_provenance": provenance})
    payload = rebuilt.model_dump()
    payload["calculation_revision_id"] = derive_calculation_revision_id_from_revision(rebuilt)
    return CalculationRevision.model_validate(payload)


def _blocking(report: VerificationReport) -> list[tuple[str, dict[str, object]]]:
    rows: list[tuple[str, dict[str, object]]] = []
    for finding in report.findings:
        if finding.severity is ModeloVerificationFindingSeverity.BLOCKING:
            facts: dict[str, object] = dict(finding.message_facts)
            rows.append((finding.message_locale_key, facts))
    return sorted(rows, key=repr)


def _verify_collection_year(
    tmp_path: Path, *, capture: bool, operation: PinnedAuthorityOperation
) -> VerificationReport:
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR + 1, operation=operation) as bucket:
        persist_manual_row(bucket.objects, filing_year=CAPITAL_YEAR + 1)
        if capture:
            capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        return _verify(revision.calculation_revision_id, operation=operation)


def test_verify_reports_a_settled_row_as_a_warning_that_changes_no_verification_outcome(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Beside the same hand-declared row, the captured coupon adds one advisory and nothing that decides granting."""
    ordinary = _verify_collection_year(tmp_path / "ordinary", capture=False, operation=operation)
    settled = _verify_collection_year(tmp_path / "settled", capture=True, operation=operation)

    (finding,) = _settled_row_findings(settled)
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.message_facts["settled_prior_accrual_rows"] == 1
    assert finding.message_facts["filing_year"] == CAPITAL_YEAR + 1
    assert _settled_row_findings(ordinary) == []
    assert _blocking(settled) == _blocking(ordinary)
    assert settled.completeness_status is ordinary.completeness_status
    assert settled.granted_verificado_completo is ordinary.granted_verificado_completo


def test_file_refuses_a_settled_row_revision_with_a_typed_reason_and_writes_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The refusal comes before every lifecycle check and leaves no filing record, pointer, event or state change."""
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR + 1, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)

        with pytest.raises(Modelo193SettledRowAmountAuthorityUnresolvedError) as exc_info:
            _file(revision.calculation_revision_id, operation=operation)

        after = stored_revision(bucket, revision.calculation_revision_id)
        records = ModeloRecordCatalogueRepository(bucket_id=BUCKET_ID, objects=bucket.objects).load().records
        work_unit = _stored_work_unit(bucket)
        filed = _filed_events(bucket)

    error = exc_info.value
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == f"{_FILE_LEAF}.m193_settled_row_amount_authority.resolved"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert error.precondition_failure is not None
    assert error.precondition_failure.subject_leaf_key == _FILE_LEAF
    assert error.precondition_failure.scenario_id == f"{_FILE_LEAF}.m193_settled_row_amount_authority.unresolved"
    (condition_evidence,) = verdict.evidence
    assert condition_evidence.values["settled_prior_accrual_rows"] == 1
    assert condition_evidence.values["amount_authority_resolved"] is False
    assert condition_evidence.values["year"] == CAPITAL_YEAR + 1
    assert get_registered_error_code(error).code == "REFUSED_MODELO_193_SETTLED_ROW_AMOUNT_AUTHORITY_UNRESOLVED"
    assert after == revision
    assert records == {}
    assert work_unit.current_filing_record_id is None
    assert work_unit.filed_calculation_revision_id is None
    assert filed == []


def test_a_pending_row_in_its_accrual_year_draws_no_finding_and_no_filing_refusal(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same coupon is a pending row of its accrual year: its persisted accrual year says so, and nothing refuses it."""
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        report = _verify(revision.calculation_revision_id, operation=operation)

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _file(revision.calculation_revision_id, operation=operation)

        work_unit = _stored_work_unit(bucket)

    (contributor,) = _phase_contributors(revision)
    assert contributor.source_filing_year == CAPITAL_YEAR
    assert modelo_193_settled_prior_accrual_contributors(work_unit, revision) == ()
    assert _settled_row_findings(report) == []


def test_the_persisted_accrual_year_decides_the_settled_row_exactly(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A collection-year contributor accrued the year before is settled; one accrued that year is pending, though the year can hold both."""
    with m193_bucket(tmp_path, filing_year=CAPITAL_YEAR + 1, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        work_unit = _stored_work_unit(bucket)

    (contributor,) = _phase_contributors(revision)
    assert contributor.source_filing_year == CAPITAL_YEAR
    assert modelo_193_settled_prior_accrual_contributors(work_unit, revision) == (contributor,)
    same_year = _with_source_filing_years(revision, CAPITAL_YEAR + 1)
    assert modelo_193_settled_prior_accrual_contributors(work_unit, same_year) == ()


@pytest.mark.parametrize("filing_year", [CAPITAL_YEAR, CAPITAL_YEAR + 1])
def test_a_revision_persisted_without_the_accrual_year_keeps_the_conservative_rule(
    tmp_path: Path, *, operation: PinnedAuthorityOperation, filing_year: int
) -> None:
    """Without the recorded year, the filing year decides through the grounded accrual-year bound.

    Every supported year after the first grounded accrual year can hold a settled
    prior-accrual row, so a contributor that lost its accrual year is counted as
    settled there even when it is the pending row: the gate over-refuses rather
    than lets a settled row through.
    """
    settled_rows = 1
    with m193_bucket(tmp_path, filing_year=filing_year, operation=operation) as bucket:
        capture_coupon_collected_next_year(bucket.objects)
        revision = calculate_m193_revision(bucket)
        work_unit = _stored_work_unit(bucket)

    legacy = _with_source_filing_years(revision, None)
    assert [ref.source_filing_year for ref in _phase_contributors(legacy)] == [None]
    assert legacy.calculation_revision_id != revision.calculation_revision_id
    assert len(modelo_193_settled_prior_accrual_contributors(work_unit, legacy)) == settled_rows
