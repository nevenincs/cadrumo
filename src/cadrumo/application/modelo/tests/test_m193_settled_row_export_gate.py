"""A Modelo 193 revision carrying a settled prior-accrual row is never written out as a fichero.

A key B coupon exigible in 2025 and collected in January 2026 is a pending row
of the 2025 Modelo 193 and a settled prior-accrual row of the 2026 one. No
official source settles the base and withholding the payment-year record
declares, so export refuses that 2026 revision from what it persisted. The
2025 revision carrying the pending row, and a 2026 revision of manual rows
only, pass the refusal. Real encrypted store, producer, calculation and export
services over the published authority.
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
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.tests._modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.tests.file_flow_test_support import calculation_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.ledger_payment_withholding import build_ledger_payment_withholding_capture
from cadrumo.application.aggregation.m193_phase_materialization import (
    modelo_193_phase_rows_may_settle_prior_accruals,
)
from cadrumo.application.aggregation.percepciones_observations_repository import (
    PercepcionObservationPorts,
    persist_percepcion_observations,
)
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.tests.ledger_capital_support import (
    capital_payment,
    capital_pending_payment,
    capital_request,
    withholding_producer,
)
from cadrumo.application.aggregation.withholding_source import WithholdingSourceResolver
from cadrumo.application.modelo.action_errors import CalculationRevisionStateError
from cadrumo.application.modelo.calculate_input import WorkCalculateInputBundle, calculate_modelo_work_revision
from cadrumo.application.modelo.export import (
    Modelo193SettledRowAmountAuthorityUnresolvedError,
    ModeloExportCommand,
    export_modelo_revision,
)
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
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000193"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_LEAF = "modelo.export"
_MANUAL_NIF = "33333333P"


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
    )
    assert withholding_producer(objects).capture(capture.command) is not None


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


def _phase_contributors(revision: CalculationRevision) -> int:
    return sum(
        1
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


def _export(
    bucket: _Bucket,
    revision_id: CalculationRevisionId,
    output_path: Path,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    export_modelo_revision(
        ModeloExportCommand(calculation_revision_id=revision_id, output_path=output_path, actor="test"),
        workflow_profile=_workflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET_ID, secure_objects=bucket.objects),
        operation=operation,
    )


def _exported_events(bucket: _Bucket) -> list[str]:
    catalogue = BucketEventHistoryRepository(objects=bucket.objects).load()
    return [
        event_id for event_id, event in catalogue.events.items() if event.event_type is BucketEventType.MODELO_EXPORTED
    ]


def test_a_settled_prior_accrual_row_refuses_export_and_writes_nothing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The refusal is typed, has no command action, and leaves no fichero, event or state change."""
    export_path = tmp_path / "modelo-193-2026-0A.txt"
    with _m193_bucket(tmp_path, filing_year=2026, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        assert _phase_contributors(revision) == 1

        with pytest.raises(Modelo193SettledRowAmountAuthorityUnresolvedError) as exc_info:
            _export(bucket, revision.calculation_revision_id, export_path, operation=operation)

        after = _stored_revision(bucket, revision.calculation_revision_id)
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
    assert condition_evidence.values["year"] == 2026
    assert get_registered_error_code(error).code == "REFUSED_MODELO_193_SETTLED_ROW_AMOUNT_AUTHORITY_UNRESOLVED"
    assert not export_path.exists()
    assert list(tmp_path.glob("modelo-193-2026-0A*")) == []
    assert exported == []
    assert after == revision


def test_a_pending_row_in_its_accrual_year_is_not_refused_by_the_settled_row_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The same coupon is a pending row in 2025, so export proceeds past the gate to its later checks."""
    with _m193_bucket(tmp_path, filing_year=2025, operation=operation) as bucket:
        _capture_coupon_collected_next_year(bucket.objects)
        revision = _calculate(bucket)
        assert _phase_contributors(revision) == 1

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _export(bucket, revision.calculation_revision_id, tmp_path / "modelo-193-2025-0A.txt", operation=operation)


def test_ordinary_rows_in_a_payment_year_are_not_refused_by_the_settled_row_gate(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A 2026 revision of hand-declared rows carries no phase contributor, so the gate passes it."""
    with _m193_bucket(tmp_path, filing_year=2026, operation=operation) as bucket:
        _persist_manual_row(bucket.objects, filing_year=2026)
        revision = _calculate(bucket)
        assert _phase_contributors(revision) == 0

        # The draft is unverified, so the lifecycle check that follows the gate refuses it.
        with pytest.raises(CalculationRevisionStateError):
            _export(bucket, revision.calculation_revision_id, tmp_path / "modelo-193-2026-0A.txt", operation=operation)


@pytest.mark.parametrize(
    ("filing_year", "may_settle"),
    [(2024, False), (2025, False), (2026, True), (2027, True)],
)
def test_only_a_year_after_the_grounded_accrual_year_can_hold_a_settled_row(
    filing_year: int, *, may_settle: bool
) -> None:
    """The phase materialisation's accrual-year bound is what tells a settled row from a pending one."""
    assert modelo_193_phase_rows_may_settle_prior_accruals(filing_year) is may_settle
