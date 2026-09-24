"""A Modelo 193 settled prior-accrual row is refused at local filing and reported at verification.

A key B coupon exigible in 2025 and collected in January 2026 is a pending row
of the 2025 Modelo 193 and a settled prior-accrual row of the 2026 one. Local
filing refuses the 2026 revision with the export gate's typed reason, and
verification reports the same detection as a non-blocking finding. The
revision persists the contributor's accrual year, so the gates tell a settled
row from a pending one exactly; a revision persisted without it falls back to
the conservative filing-year rule. Real encrypted store, producer, calculation,
verification and filing services over the published authority.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.tests.ledger_capital_support import (
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.percepciones_observations_repository import (
    PercepcionObservationPorts,
    persist_percepcion_observations,
)
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    quarterly_filer_cadence,
    quarterly_filer_cadence_for,
)
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.filing_actions import file_modelo_revision
from cadrumo.application.modelo.m193_settled_row_gate import (
    Modelo193SettledRowAmountAuthorityUnresolvedError,
    modelo_193_settled_prior_accrual_contributors,
)
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.aggregation import (
    AggregationCaptureKind,
    BindingSourceKind,
    CalculationSourceLineageRole,
    RetencionScheme,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.identity.hex_ids import CalculationRevisionId
from cadrumo.core.operator_action_enums import NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationSourceRef,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition import build_filing_action_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000193"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_FILE_LEAF = "modelo.work.file"
_MANUAL_NIF = "33333333P"
_FINDING_KEY = "application.modelo.findings.m193_settled_row_amount_authority_unresolved"


@dataclass(frozen=True, slots=True)
class _Bucket:
    objects: SecureObjectRepository
    filing_year: int
    work_unit_id: str


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="capital income payer"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=profile_creation_context_for_test(),
        ),
    )


@contextmanager
def _m193_bucket(tmp_path: Path, *, filing_year: int, operation: PinnedAuthorityOperation) -> Iterator[_Bucket]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="M193 settled row") as profile:
        objects: SecureObjectRepository = profile.repository
        _seed_ready_profile(objects)
        snapshot = operation.snapshot("193", filing_year=filing_year, period="0A")
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="193",
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
            revision_id=snapshot.revision.id,
            ports=WorkLifecyclePorts(
                work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            clock=_T0,
            operation=operation,
        )
        yield _Bucket(objects=objects, filing_year=filing_year, work_unit_id=work_unit.work_unit_id)


def _capture_coupon_collected_next_year(objects: SecureObjectRepository) -> None:
    """Capture a key B coupon exigible on 15 December 2025 and collected on 20 January 2026."""
    paid_on = date(2026, 1, 20)
    transaction = capital_payment(provider_id="coupon-2025-12", booked_date=paid_on)
    capture = build_ledger_payment_withholding_capture(
        transaction,
        catalogue_revision_id="c" * 64,
        request=capital_request(
            transaction,
            payment_event_id="coupon-payment-2026-01",
            exigibility_occurred_on=date(2025, 12, 15),
            modelo_193_pending_payment=capital_pending_payment(transaction, transaction_date=paid_on),
        ),
        applicable_year=2025,
        cadence=quarterly_filer_cadence(2025),
    )
    assert (
        withholding_producer(objects).capture(capture.command, cadence=quarterly_filer_cadence_for(capture.command))
        is not None
    )


def _persist_manual_row(objects: SecureObjectRepository, *, filing_year: int) -> None:
    """Declare one ordinary key B row by hand for a second, synthetic holder."""
    template = capital_pending_payment(
        capital_payment(provider_id="manual-coupon"),
        transaction_date=date(filing_year, 5, 5),
    ).actual_recipient_detail
    persist_percepcion_observations(
        ports=PercepcionObservationPorts(repository=PercepcionObservationRepositoryAdapter(objects=objects)),
        modelo="193",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        observations=[
            template.model_copy(
                update={
                    "source_id": "manual-coupon",
                    "source_allocation_id": "manual-1",
                    "perceptor_tax_id": _MANUAL_NIF,
                    "perceptor_legal_name": "Perceptor Manual Sintetico",
                }
            )
        ],
    )


def _seed_declarant_retenciones(objects: SecureObjectRepository, *, filing_year: int) -> None:
    """Store the retenciones the 193 declarant totals read from its own annual window."""
    RetencionObservationRepositoryAdapter(objects=objects).replace_observations(
        modelo="193",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id=f"declarant-{filing_year}",
                perceptor_nif=_MANUAL_NIF,
                perceptor_name="Perceptor Manual Sintetico",
                scheme=RetencionScheme("intereses"),
                taxable_base=Decimal("1000.00"),
                retencion_amount=Decimal("190.00"),
                accrued_on=f"{filing_year}-05-05",
            )
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _calculate(bucket: _Bucket) -> CalculationRevision:
    _seed_declarant_retenciones(bucket.objects, filing_year=bucket.filing_year)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=bucket.objects),
        invoice_repository=InvoiceCatalogueRepository(objects=bucket.objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects),
        work_unit_repository=WorkUnitCatalogueRepository(objects=bucket.objects),
    ) as ports:
        result = calculate_modelo_work_revision(
            work_unit_id=bucket.work_unit_id,
            actor="test",
            inputs=WorkCalculateInputBundle.build(
                casilla_inputs={},
                binding_values={},
                enum_binding_values={},
                relation_values={},
                detail_rows=(),
                borrador_snapshot_id=None,
            ),
            ports=ports,
        )
    return _stored_revision(bucket, result.revision.calculation_revision_id)


def _stored_revision(bucket: _Bucket, revision_id: CalculationRevisionId) -> CalculationRevision:
    revision = (
        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().get(revision_id)
    )
    assert revision is not None
    return revision


def _stored_work_unit(bucket: _Bucket) -> WorkUnit:
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


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        activity_start_date=date(2020, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _verify(revision_id: CalculationRevisionId, *, operation: PinnedAuthorityOperation) -> VerificationReport:
    return verify_modelo_revision_with_preconditions(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        actor="test",
        workflow_profile=_workflow_profile(),
        verification_repositories=build_test_verification_repository_bundle(),
        operation=operation,
    ).report


def _file(revision_id: CalculationRevisionId, *, operation: PinnedAuthorityOperation) -> None:
    file_modelo_revision(
        revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        operator_scope_ports=build_operator_scope_ports(),
        ports=build_filing_action_ports(bucket_id=_BUCKET_ID),
        actor="test",
        workflow_profile=_workflow_profile(),
        operation=operation,
    )


def _settled_row_findings(report: VerificationReport) -> list[ModeloVerificationFinding]:
    return [finding for finding in report.findings if finding.message_locale_key == _FINDING_KEY]


def _filed_events(bucket: _Bucket) -> list[str]:
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
    return sorted(
        (
            (finding.message_locale_key, dict(finding.message_facts))
            for finding in report.findings
            if finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        ),
        key=repr,
    )


def _verify_2026(tmp_path: Path, *, capture: bool, operation: PinnedAuthorityOperation) -> VerificationReport:
    with _m193_bucket(tmp_path, filing_year=2026, operation=operation) as bucket:
        _persist_manual_row(bucket.objects, filing_year=2026)
        if capture:
            _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        return _verify(revision.calculation_revision_id, operation=operation)


def test_verify_reports_a_settled_row_as_a_warning_that_changes_no_verification_outcome(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Beside the same hand-declared row, the captured coupon adds one advisory and nothing that decides granting."""
    ordinary = _verify_2026(tmp_path / "ordinary", capture=False, operation=operation)
    settled = _verify_2026(tmp_path / "settled", capture=True, operation=operation)

    (finding,) = _settled_row_findings(settled)
    assert finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.message_facts["settled_prior_accrual_rows"] == 1
    assert finding.message_facts["filing_year"] == 2026
    assert _settled_row_findings(ordinary) == []
    assert _blocking(settled) == _blocking(ordinary)
    assert settled.completeness_status is ordinary.completeness_status
    assert settled.granted_verificado_completo is ordinary.granted_verificado_completo


def test_file_refuses_a_settled_row_revision_with_a_typed_reason_and_writes_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The refusal comes before every lifecycle check and leaves no filing record, pointer, event or state change."""
    with _m193_bucket(tmp_path, filing_year=2026, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)

        with pytest.raises(Modelo193SettledRowAmountAuthorityUnresolvedError) as exc_info:
            _file(revision.calculation_revision_id, operation=operation)

        after = _stored_revision(bucket, revision.calculation_revision_id)
        records = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID, objects=bucket.objects).load().records
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
    assert condition_evidence.values["year"] == 2026
    assert get_registered_error_code(error).code == "REFUSED_MODELO_193_SETTLED_ROW_AMOUNT_AUTHORITY_UNRESOLVED"
    assert after == revision
    assert records == {}
    assert work_unit.current_filing_record_id is None
    assert work_unit.filed_calculation_revision_id is None
    assert filed == []


def test_a_pending_row_in_its_accrual_year_draws_no_finding_and_no_filing_refusal(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same coupon is a pending row of 2025: its persisted accrual year says so, and nothing refuses it."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        report = _verify(revision.calculation_revision_id, operation=operation)

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _file(revision.calculation_revision_id, operation=operation)

        work_unit = _stored_work_unit(bucket)

    (contributor,) = _phase_contributors(revision)
    assert contributor.source_filing_year == 2025
    assert modelo_193_settled_prior_accrual_contributors(work_unit, revision) == ()
    assert _settled_row_findings(report) == []


def test_the_persisted_accrual_year_decides_the_settled_row_exactly(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A 2026 contributor accrued in 2025 is settled; one accrued in 2026 is pending, although 2026 can hold both."""
    with _m193_bucket(tmp_path, filing_year=2026, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        work_unit = _stored_work_unit(bucket)

    (contributor,) = _phase_contributors(revision)
    assert contributor.source_filing_year == 2025
    assert modelo_193_settled_prior_accrual_contributors(work_unit, revision) == (contributor,)
    same_year = _with_source_filing_years(revision, 2026)
    assert modelo_193_settled_prior_accrual_contributors(work_unit, same_year) == ()


@pytest.mark.parametrize(("filing_year", "settled_rows"), [(2025, 0), (2026, 1)])
def test_a_revision_persisted_without_the_accrual_year_keeps_the_conservative_rule(
    tmp_path: Path, *, operation: PinnedAuthorityOperation, filing_year: int, settled_rows: int
) -> None:
    """Without the recorded year, the filing year decides through the grounded accrual-year bound."""
    with _m193_bucket(tmp_path, filing_year=filing_year, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        work_unit = _stored_work_unit(bucket)

    legacy = _with_source_filing_years(revision, None)
    assert [ref.source_filing_year for ref in _phase_contributors(legacy)] == [None]
    assert legacy.calculation_revision_id != revision.calculation_revision_id
    assert len(modelo_193_settled_prior_accrual_contributors(work_unit, legacy)) == settled_rows
