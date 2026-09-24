"""Operational producer-to-Modelo-111 proof over encrypted withholding storage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.m193_phase_materialization import (
    Modelo193DisclosurePhase,
    materialize_modelo_193_disclosure_phases,
)
from cadrumo.application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.aggregation.retenciones import (
    Modelo180PropertyEvidence,
    Modelo180StructuredAddress,
    Modelo193NonpaymentCause,
    Modelo193PendingPaymentEvidence,
    aggregate_retenciones_180,
)
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.withholding_observation_service import (
    ABSENT_WITHHOLDING_GENERATION_ID,
    SourceLiabilitySnapshot,
    WithholdingMutationMode,
    WithholdingObservationMutationError,
    WithholdingObservationService,
    WithholdingWindowScope,
)
from cadrumo.application.aggregation.withholding_producer import (
    WithholdingEvidenceCaptureCommand,
    WithholdingProducer,
    WithholdingProducerError,
)
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingDatedEvent,
    WithholdingIncomeKind,
    WithholdingOperationKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionError,
    WithholdingRecognitionEvidence,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]
_PROFESSIONAL_SCHEME = RetencionScheme("actividades_profesionales")
_CAPITAL_SCHEME = RetencionScheme("intereses")


def _producer_for(objects: object) -> tuple[WithholdingProducer, WithholdingObservationService]:
    from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

    assert isinstance(objects, SecureObjectRepository)
    service = WithholdingObservationService(
        WithholdingObservationWorkflowAdapter(
            objects=objects,
            retenciones=RetencionObservationRepositoryAdapter(objects=objects),
            percepciones=PercepcionObservationRepositoryAdapter(objects=objects),
        )
    )
    return WithholdingProducer(service=service), service


def _command(
    *,
    allocation_id: str = "allocation-1",
    payment_id: str = "payment-1",
    paid_on: date = date(2025, 4, 2),
    taxable_base: str = "300.00",
    retencion_amount: str = "57.00",
    income_kind: WithholdingIncomeKind = WithholdingIncomeKind.PROFESSIONAL,
    scheme: RetencionScheme = _PROFESSIONAL_SCHEME,
    recipient_status: WithholdingRecipientTaxStatus = WithholdingRecipientTaxStatus.RESIDENT,
    settlement_amount: str | None = None,
    liability_base: str = "500.00",
    liability_withholding: str = "95.00",
    liability_settlement: str = "500.00",
    property_detail: Modelo180PropertyEvidence | None = None,
    modelo_190_detail: WithholdingObservation | object | None = ...,
) -> WithholdingEvidenceCaptureCommand:
    if modelo_190_detail is ...:
        annual_detail = (
            _annual_detail(
                payment_id=payment_id,
                taxable_base=taxable_base,
                retencion_amount=retencion_amount,
                paid_on=paid_on,
            )
            if income_kind in {WithholdingIncomeKind.WORK, WithholdingIncomeKind.PROFESSIONAL}
            else None
        )
    else:
        annual_detail = modelo_190_detail
    return WithholdingEvidenceCaptureCommand(
        # This source intentionally represents a March-issued payable invoice;
        # payment evidence, rather than an invoice timestamp, chooses 2025 2T.
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id="invoice-issued-2025-03-31",
        source_revision_id="invoice-revision-1",
        allocation_id=allocation_id,
        perceptor_nif="11111111H",
        perceptor_name="Professional Recipient",
        scheme=scheme,
        taxable_base=Decimal(taxable_base),
        retencion_amount=Decimal(retencion_amount),
        settlement_amount=Decimal(settlement_amount or taxable_base),
        liability_snapshot=SourceLiabilitySnapshot(
            source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            source_object_id="invoice-issued-2025-03-31",
            source_revision_id="invoice-revision-1",
            liability_base=Decimal(liability_base),
            liability_withholding=Decimal(liability_withholding),
            liability_settlement=Decimal(liability_settlement),
        ),
        recognition_evidence=WithholdingRecognitionEvidence(
            applicable_year=2025,
            recipient_tax_status=recipient_status,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            income_kind=income_kind,
            operation_kind=WithholdingOperationKind.ORDINARY,
            payment_or_satisfaction=WithholdingDatedEvent(event_id=payment_id, occurred_on=paid_on),
        ),
        idempotency_key=f"capture-{allocation_id}",
        modelo_180_property=property_detail,
        modelo_190_detail=annual_detail,
    )


def _capital_command(
    *,
    allocation_id: str = "capital-allocation-1",
    scheme: RetencionScheme = _CAPITAL_SCHEME,
    payment_id: str | None = None,
    paid_on: date | None = None,
    exigibility_id: str = "capital-exigibility-2025-12",
    exigible_on: date = date(2025, 12, 15),
    settlement_amount: str = "0.00",
    modelo_193_pending_payment: Modelo193PendingPaymentEvidence | None = None,
) -> WithholdingEvidenceCaptureCommand:
    """Build one resident-IRPF capital allocation with explicit due evidence."""
    return WithholdingEvidenceCaptureCommand(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id="capital-invoice-2025-12",
        source_revision_id="capital-invoice-revision-1",
        allocation_id=allocation_id,
        perceptor_nif="11111111H",
        perceptor_name="Resident Capital Recipient",
        scheme=scheme,
        taxable_base=Decimal("500.00"),
        retencion_amount=Decimal("95.00"),
        settlement_amount=Decimal(settlement_amount),
        liability_snapshot=SourceLiabilitySnapshot(
            source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            source_object_id="capital-invoice-2025-12",
            source_revision_id="capital-invoice-revision-1",
            liability_base=Decimal("500.00"),
            liability_withholding=Decimal("95.00"),
            liability_settlement=Decimal("405.00"),
        ),
        recognition_evidence=WithholdingRecognitionEvidence(
            applicable_year=2025,
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
            operation_kind=WithholdingOperationKind.ORDINARY,
            exigibility=WithholdingDatedEvent(event_id=exigibility_id, occurred_on=exigible_on),
            payment_or_satisfaction=(
                WithholdingDatedEvent(event_id=payment_id, occurred_on=paid_on)
                if payment_id is not None and paid_on is not None
                else None
            ),
        ),
        idempotency_key=f"capital-capture-{allocation_id}",
        modelo_193_pending_payment=modelo_193_pending_payment,
    )


def _annual_detail(
    *,
    payment_id: str,
    taxable_base: str,
    retencion_amount: str,
    paid_on: date,
    clave: str = "G",
    subclave: str = "",
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id="invoice-issued-2025-03-31",
        perceptor_tax_id="11111111H",
        perceptor_legal_name="Professional Recipient",
        transaction_date=paid_on,
        clave=RetencionClave.from_registry(clave),
        subclave=subclave,
        percibido_dinerario=Decimal(taxable_base),
        retencion_practicada=Decimal(retencion_amount),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal(taxable_base),
        porcentaje_retencion=Decimal("19"),
    )


def _capital_pending_payment_detail(*, transaction_date: date) -> Modelo193PendingPaymentEvidence:
    """Build the actual-recipient facts retained behind the 2025 pending row."""
    return Modelo193PendingPaymentEvidence(
        perception_key="B",
        nonpayment_cause=Modelo193NonpaymentCause.HOLDER_NOT_PRESENTED_FOR_COLLECTION,
        actual_recipient_detail=WithholdingObservation(
            source_id="capital-invoice-2025-12",
            perceptor_tax_id="11111111H",
            perceptor_legal_name="Resident Capital Recipient",
            transaction_date=transaction_date,
            clave=RetencionClave.from_registry("B"),
            percibido_dinerario=Decimal("500.00"),
            retencion_practicada=Decimal("95.00"),
            incapacity_cash_perception=Decimal("0"),
            incapacity_cash_withholding=Decimal("0"),
            incapacity_kind_value=Decimal("0"),
            incapacity_kind_ingreso_a_cuenta=Decimal("0"),
            incapacity_kind_repercutido=Decimal("0"),
            foral_retention_estatal=Decimal("0"),
            foral_retention_navarra=Decimal("0"),
            foral_retention_araba=Decimal("0"),
            foral_retention_gipuzkoa=Decimal("0"),
            foral_retention_bizkaia=Decimal("0"),
            base_retenciones=Decimal("500.00"),
            porcentaje_retencion=Decimal("19"),
            clave_codigo=4,
            naturaleza="03",
            pago=1,
            tipo_codigo="C",
            tipo_percepcion=1,
            clave_mercado="A",
        ),
    )


def _rent_property(key: str, cadastral_reference: str) -> Modelo180PropertyEvidence:
    return Modelo180PropertyEvidence(
        property_key=key,
        situation="1",
        cadastral_reference=cadastral_reference,
        recipient_province_code="28",
        modality="1",
        accrual_year=2025,
        withholding_percentage=Decimal("19.00"),
        address=Modelo180StructuredAddress(
            province_code="28",
            municipality_code="079",
            municipality="Madrid",
            locality="Madrid",
            postal_code="28001",
            street_type="CL",
            street_name="Ejemplo",
            number_type="NUM",
            house_number="1",
        ),
    )


def test_professional_payment_producer_reopens_and_feeds_pinned_m111_resolver(tmp_path: Path) -> None:
    """Two partial 2T payments feed Modelo 111, despite a 1T invoice source."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, _service = _producer_for(profile.repository)
        first = producer.capture(_command())
        second = producer.capture(
            _command(
                allocation_id="allocation-2",
                payment_id="payment-2",
                paid_on=date(2025, 6, 30),
                taxable_base="200.00",
                retencion_amount="38.00",
            )
        )

        assert first is not None and first.scope.period == Period.from_year_and_code(2025, "2T")
        assert first.recognition.recognized_on == date(2025, 4, 2)
        assert second is not None and second.scope == first.scope

        _reopened_producer, reopened_service = _producer_for(profile.repository)
        state = reopened_service.read_window(first.scope)
        assert len(state.entries) == 4
        persisted = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(2025, "2T")
        )
        assert len(persisted) == 2
        assert {row.accrued_on for row in persisted} == {"2025-04-02", "2025-06-30"}
        annual_detail = PercepcionObservationRepositoryAdapter(
            objects=profile.repository
        ).load_annual_source_observations("111", 2025)
        assert len(annual_detail) == 2
        assert {row.clave for row in annual_detail} == {RetencionClave.from_registry("G")}
        assert {row.source_allocation_id for row in annual_detail} == {"allocation-1", "allocation-2"}
        assert sum((row.percibido_dinerario for row in annual_detail), Decimal("0")) == Decimal("500.00")
        assert sum((row.retencion_practicada for row in annual_detail), Decimal("0")) == Decimal("95.00")

        with bundled_indexed_authority().operation() as operation:
            snapshot = operation.snapshot("111", filing_year=2025, period="2T")
            resolution = RetencionesAggregationSourceResolver(
                ports=RetencionObservationPorts(
                    repository=RetencionObservationRepositoryAdapter(objects=profile.repository)
                )
            ).resolve(
                CalculationSourceContext(
                    bucket_id="synthetic-professional-producer",
                    modelo="111",
                    filing_year=2025,
                    period=Period.from_year_and_code(2025, "2T"),
                    revision=snapshot.revision,
                )
            )

        assert resolution.binding_values["modelo-111-actividades-dinerario-perceptores"] == Decimal("1")
        assert resolution.binding_values["modelo-111-actividades-dinerario-base"] == Decimal("500.00")
        assert resolution.binding_values["modelo-111-actividades-dinerario-retenciones"] == Decimal("95.00")


def test_unpaid_exigible_capital_reopens_and_later_settlement_does_not_duplicate_123_liability(
    tmp_path: Path,
) -> None:
    """One active allocation yields both accepted annual phases without another 123 row."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, _service = _producer_for(profile.repository)
        unpaid = producer.capture(
            _capital_command(
                modelo_193_pending_payment=_capital_pending_payment_detail(transaction_date=date(2025, 12, 15))
            )
        )

        assert unpaid is not None
        assert unpaid.scope == WithholdingWindowScope(
            modelo="123",
            period=Period.from_year_and_code(2025, "4T"),
        )
        assert unpaid.recognition.recognized_on == date(2025, 12, 15)
        assert unpaid.recognition.recognition_event_id == "capital-exigibility-2025-12"
        assert unpaid.recognition.settlement_event_id is None

        reopened_producer, reopened_service = _producer_for(profile.repository)
        before_settlement = reopened_service.read_window(unpaid.scope)
        assert len(before_settlement.entries) == 1
        persisted = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "123", unpaid.scope.period
        )
        assert len(persisted) == 1
        assert persisted[0].accrued_on == "2025-12-15"
        assert persisted[0].modelo_193_capital is not None
        assert persisted[0].modelo_193_capital.settlement_event is None
        pending_at_accrual = materialize_modelo_193_disclosure_phases(persisted, filing_year=2025)
        assert len(pending_at_accrual) == 1
        pending = pending_at_accrual[0]
        assert pending.phase is Modelo193DisclosurePhase.PENDING
        assert pending.annual_detail.perceptor_tax_id == "999999999"
        assert pending.annual_detail.representative_tax_id == "999999999"
        assert pending.annual_detail.perceptor_legal_name == "VALORES PENDIENTE DE ABONO"
        assert pending.annual_detail.pendiente_flag == "X"
        assert pending.taxable_base == Decimal("500.00")
        assert pending.retencion_amount == Decimal("95.00")

        settled_command = _capital_command(
            payment_id="capital-settlement-2026-01",
            paid_on=date(2026, 1, 20),
            settlement_amount="405.00",
            modelo_193_pending_payment=_capital_pending_payment_detail(transaction_date=date(2026, 1, 20)),
        ).model_copy(
            update={
                "mode": WithholdingMutationMode.REPLACE,
                "baseline": unpaid.mutation.baseline,
                "reason": "synthetic later capital settlement",
                "supersedes_generation_id": unpaid.mutation.baseline.generation_id,
                "idempotency_key": "capital-settlement-capture-2026-01",
            }
        )
        settled = reopened_producer.capture(settled_command)

        assert settled is not None
        assert settled.scope == unpaid.scope
        assert settled.recognition.recognized_on == date(2025, 12, 15)
        assert settled.recognition.recognition_event_id == unpaid.recognition.recognition_event_id
        assert settled.recognition.settlement_event_id == "capital-settlement-2026-01"
        after_settlement = reopened_service.read_window(unpaid.scope)
        assert len(after_settlement.entries) == 1
        assert after_settlement.entries[0].identity.settlement_event_id == "capital-settlement-2026-01"
        assert after_settlement.entries[0].allocation.allocated_settlement == Decimal("405.00")
        assert after_settlement.entries[0].retencion is not None
        assert after_settlement.entries[0].retencion.modelo_193_capital is not None
        assert after_settlement.entries[0].retencion.modelo_193_capital.settlement_event == WithholdingDatedEvent(
            event_id="capital-settlement-2026-01",
            occurred_on=date(2026, 1, 20),
        )

        _after_reopen_producer, after_reopen_service = _producer_for(profile.repository)
        persisted_after_settlement = RetencionObservationRepositoryAdapter(
            objects=profile.repository
        ).load_observations("123", unpaid.scope.period)
        assert len(persisted_after_settlement) == 1
        assert len(after_reopen_service.read_window(unpaid.scope).entries) == 1
        aggregation = RetencionesAggregationSourceResolver.aggregate(
            "123", persisted_after_settlement, period=unpaid.scope.period
        )
        assert aggregation.total_taxable_base == Decimal("500.00")
        assert aggregation.total_retencion == Decimal("95.00")
        assert {row.scheme for row in aggregation.rollups} == {RetencionScheme("intereses")}

        pending_after_settlement = materialize_modelo_193_disclosure_phases(
            persisted_after_settlement,
            filing_year=2025,
        )
        settlement_phase = materialize_modelo_193_disclosure_phases(
            persisted_after_settlement,
            filing_year=2026,
        )
        assert [row.phase for row in pending_after_settlement] == [Modelo193DisclosurePhase.PENDING]
        assert [row.phase for row in settlement_phase] == [Modelo193DisclosurePhase.SETTLED_PRIOR_ACCRUAL]
        settled_row = settlement_phase[0]
        assert settled_row.original_accrual_year == 2025
        assert settled_row.settlement_event_id == "capital-settlement-2026-01"
        assert settled_row.annual_detail.perceptor_tax_id == "11111111H"
        assert settled_row.annual_detail.accrual_year == 2025
        assert settled_row.annual_detail.pendiente_flag is None
        assert settled_row.filing_export_supported is False
        assert materialize_modelo_193_disclosure_phases(persisted_after_settlement, filing_year=2027) == ()

        replay = reopened_producer.capture(settled_command)
        assert replay is not None and replay.mutation.replayed
        assert len(reopened_service.read_window(unpaid.scope).entries) == 1

        stale = settled_command.model_copy(
            update={
                "baseline": unpaid.mutation.baseline,
                "idempotency_key": "capital-stale-settlement-capture",
            }
        )
        with pytest.raises(WithholdingObservationMutationError, match="stale_baseline"):
            reopened_producer.capture(stale)
        assert len(reopened_service.read_window(unpaid.scope).entries) == 1

        audit = reopened_service.read_generation(unpaid.scope, settled.mutation.baseline.generation_id)
        assert audit is not None
        assert audit.supersedes_generation_id == unpaid.mutation.baseline.generation_id


@pytest.mark.parametrize("perception_key", ("A", "B", "D"))
def test_modelo_193_pending_evidence_accepts_only_the_grounded_2025_keys(
    perception_key: Literal["A", "B", "D"],
) -> None:
    """The special pending-payment contract never accepts an inferred clave."""
    original = _capital_pending_payment_detail(transaction_date=date(2025, 12, 15))
    annual_detail = original.actual_recipient_detail.model_copy(
        update={"clave": RetencionClave.from_registry(perception_key)}
    )

    evidence = Modelo193PendingPaymentEvidence(
        perception_key=perception_key,
        nonpayment_cause=Modelo193NonpaymentCause.HOLDER_NOT_PRESENTED_FOR_COLLECTION,
        actual_recipient_detail=annual_detail,
    )

    assert evidence.actual_recipient_detail.clave.value == perception_key


def test_modelo_193_unsupported_cause_and_same_year_settlement_refuse_before_mutation(tmp_path: Path) -> None:
    """Unsupported unpaid facts and a contradictory same-year payment leave 123 absent."""
    original = _capital_pending_payment_detail(transaction_date=date(2025, 12, 15))
    with pytest.raises(ValidationError, match="nonpayment_cause"):
        Modelo193PendingPaymentEvidence(
            perception_key="B",
            nonpayment_cause="debtor_insolvency",
            actual_recipient_detail=original.actual_recipient_detail,
        )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        contradictory = _capital_command(
            payment_id="capital-settlement-2025-12",
            paid_on=date(2025, 12, 20),
            settlement_amount="405.00",
            modelo_193_pending_payment=_capital_pending_payment_detail(transaction_date=date(2025, 12, 20)),
        )

        with pytest.raises(WithholdingProducerError, match="nonpayment_cause_conflicts_with_same_year_settlement"):
            producer.capture(contradictory)

        scope = WithholdingWindowScope(modelo="123", period=Period.from_year_and_code(2025, "4T"))
        assert service.read_window(scope).entries == ()
        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("123", scope.period)
            == ()
        )


def test_capital_exigibility_is_required_before_a_123_window_is_mutated(tmp_path: Path) -> None:
    """A payment-free capital command cannot use an invoice date as a fallback."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        command = _capital_command()
        missing_exigibility = command.model_copy(
            update={"recognition_evidence": command.recognition_evidence.model_copy(update={"exigibility": None})}
        )

        with pytest.raises(WithholdingRecognitionError, match="missing_exigibility_evidence"):
            producer.capture(missing_exigibility)

        scope = WithholdingWindowScope(modelo="123", period=Period.from_year_and_code(2025, "4T"))
        assert service.read_window(scope).entries == ()
        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("123", scope.period)
            == ()
        )


def test_capital_producer_refuses_noncapital_scheme_before_a_123_window_is_mutated(tmp_path: Path) -> None:
    """The resident capital slice admits only the selected 123 scheme catalogue."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)

        with pytest.raises(WithholdingProducerError, match="scheme_income_kind_mismatch"):
            producer.capture(_capital_command(scheme=RetencionScheme("actividades_profesionales")))

        scope = WithholdingWindowScope(modelo="123", period=Period.from_year_and_code(2025, "4T"))
        assert service.read_window(scope).entries == ()


def test_invalid_recognition_refuses_before_any_encrypted_projection_write(tmp_path: Path) -> None:
    """Unsupported recipient evidence cannot create a partial withholding window."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        command = _command(recipient_status=WithholdingRecipientTaxStatus.NONRESIDENT)

        with pytest.raises(WithholdingRecognitionError, match="irnr_unsupported"):
            producer.capture(command)

        scope = Period.from_year_and_code(2025, "2T")
        assert RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations("111", scope) == ()
        assert (
            service.read_window(
                # The absence token proves the producer failed before the atomic
                # workflow boundary, rather than committing an empty replacement.
                WithholdingWindowScope(modelo="111", period=scope)
            ).baseline.generation_id
            == ABSENT_WITHHOLDING_GENERATION_ID
        )


def test_omitted_capture_does_not_create_a_window(tmp_path: Path) -> None:
    """Omission is a read/no-op, never an inferred empty replacement."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, _service = _producer_for(profile.repository)

        assert producer.capture(None) is None
        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                "111", Period.from_year_and_code(2025, "2T")
            )
            == ()
        )


def test_missing_modelo_190_detail_refuses_before_any_encrypted_projection_write(tmp_path: Path) -> None:
    """Professional capture cannot strand a quarterly 111 allocation from its annual detail."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)

        with pytest.raises(ValueError, match="Modelo 190 annual detail"):
            producer.capture(_command(modelo_190_detail=None))

        scope = WithholdingWindowScope(modelo="111", period=Period.from_year_and_code(2025, "2T"))
        assert service.read_window(scope).entries == ()
        assert (
            PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
                "111", 2025
            )
            == ()
        )


def test_correction_replaces_active_m111_and_m190_projections_without_erasing_history(tmp_path: Path) -> None:
    """A source correction changes the effective annual row through the same atomic generation."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        original_command = _command()
        original = producer.capture(original_command)
        assert original is not None

        corrected_liability = original_command.liability_snapshot.model_copy(
            update={"source_revision_id": "invoice-revision-2"}
        )
        corrected = original_command.model_copy(
            update={
                "source_revision_id": "invoice-revision-2",
                "taxable_base": Decimal("280.00"),
                "retencion_amount": Decimal("53.20"),
                "settlement_amount": Decimal("280.00"),
                "liability_snapshot": corrected_liability,
                "modelo_190_detail": _annual_detail(
                    payment_id="payment-1",
                    paid_on=date(2025, 4, 2),
                    taxable_base="280.00",
                    retencion_amount="53.20",
                ),
                "mode": WithholdingMutationMode.REPLACE,
                "baseline": original.mutation.baseline,
                "reason": "synthetic corrected source revision",
                "supersedes_generation_id": original.mutation.baseline.generation_id,
                "idempotency_key": "corrected-capture-1",
            }
        )
        result = producer.capture(corrected)
        assert result is not None
        state = service.read_window(result.scope)
        assert len(state.entries) == 2
        annual = PercepcionObservationRepositoryAdapter(objects=profile.repository).load_annual_source_observations(
            "111", 2025
        )
        assert len(annual) == 1
        assert annual[0].percibido_dinerario == Decimal("280.00")
        assert annual[0].retencion_practicada == Decimal("53.20")
        audit = service.read_generation(result.scope, result.mutation.baseline.generation_id)
        assert audit is not None
        assert audit.supersedes_generation_id == original.mutation.baseline.generation_id


def test_income_scheme_mismatch_refuses_without_choosing_another_modelo(tmp_path: Path) -> None:
    """A professional branch cannot smuggle a rent scheme into Modelo 111."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, _service = _producer_for(profile.repository)

        with pytest.raises(WithholdingProducerError, match="scheme_income_kind_mismatch"):
            producer.capture(_command(scheme=RetencionScheme("arrendamiento_urbano")))

        assert (
            RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
                "111", Period.from_year_and_code(2025, "2T")
            )
            == ()
        )


def _amounts_command(
    amounts: dict[str, str], *, allocation_id: str = "allocation-1", payment_id: str = "payment-1"
) -> WithholdingEvidenceCaptureCommand:
    """Build one capture from a parametrised base/withholding/settlement triple."""
    return _command(
        allocation_id=allocation_id,
        payment_id=payment_id,
        taxable_base=amounts["taxable_base"],
        retencion_amount=amounts["retencion_amount"],
        settlement_amount=amounts["settlement_amount"],
    )


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    (
        (
            {"taxable_base": "300.00", "retencion_amount": "57.00", "settlement_amount": "300.00"},
            {"taxable_base": "201.00", "retencion_amount": "38.00", "settlement_amount": "200.00"},
            "liability_base_exceeded",
        ),
        (
            {"taxable_base": "100.00", "retencion_amount": "20.00", "settlement_amount": "100.00"},
            {"taxable_base": "100.00", "retencion_amount": "76.00", "settlement_amount": "100.00"},
            "liability_withholding_exceeded",
        ),
        (
            {"taxable_base": "100.00", "retencion_amount": "19.00", "settlement_amount": "300.00"},
            {"taxable_base": "100.00", "retencion_amount": "19.00", "settlement_amount": "201.00"},
            "liability_settlement_exceeded",
        ),
    ),
)
def test_liability_dimensions_refuse_before_a_second_projection_write(
    tmp_path: Path,
    first: dict[str, str],
    second: dict[str, str],
    expected: str,
) -> None:
    """Each monetary dimension is bounded independently at the atomic boundary."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        producer.capture(_amounts_command(first))

        with pytest.raises(WithholdingObservationMutationError, match=expected):
            producer.capture(_amounts_command(second, allocation_id="allocation-2", payment_id="payment-2"))

        scope = WithholdingWindowScope(modelo="111", period=Period.from_year_and_code(2025, "2T"))
        assert len(service.read_window(scope).entries) == 2


def test_exact_liability_cap_and_replay_do_not_double_count(tmp_path: Path) -> None:
    """The exact cap succeeds once and its idempotent retry consumes no capacity."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        first = _command(taxable_base="300.00", retencion_amount="57.00", settlement_amount="300.00")
        producer.capture(first)
        replay = producer.capture(first)
        producer.capture(
            _command(
                allocation_id="allocation-2",
                payment_id="payment-2",
                taxable_base="200.00",
                retencion_amount="38.00",
                settlement_amount="200.00",
            )
        )
        assert replay is not None and replay.mutation.replayed
        assert len(service.read_window(replay.scope).entries) == 4


def test_rent_allocations_reopen_as_two_annual_property_rows(tmp_path: Path) -> None:
    """The annual materializer reads active 115 quarters, not a second annual store."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, _service = _producer_for(profile.repository)
        producer.capture(
            _command(
                allocation_id="rent-q1-a",
                payment_id="rent-payment-q1-a",
                paid_on=date(2025, 3, 20),
                taxable_base="200.00",
                retencion_amount="38.00",
                settlement_amount="200.00",
                income_kind=WithholdingIncomeKind.URBAN_RENT,
                scheme=RetencionScheme("arrendamiento_urbano"),
                property_detail=_rent_property("office-a", "1234567VK4713S0001AA"),
            )
        )
        producer.capture(
            _command(
                allocation_id="rent-q2-a",
                payment_id="rent-payment-q2-a",
                paid_on=date(2025, 4, 20),
                taxable_base="100.00",
                retencion_amount="19.00",
                settlement_amount="100.00",
                income_kind=WithholdingIncomeKind.URBAN_RENT,
                scheme=RetencionScheme("arrendamiento_urbano"),
                property_detail=_rent_property("office-a", "1234567VK4713S0001AA"),
            )
        )
        producer.capture(
            _command(
                allocation_id="rent-q2-b",
                payment_id="rent-payment-q2-b",
                paid_on=date(2025, 5, 20),
                taxable_base="200.00",
                retencion_amount="38.00",
                settlement_amount="200.00",
                income_kind=WithholdingIncomeKind.URBAN_RENT,
                scheme=RetencionScheme("arrendamiento_urbano"),
                property_detail=_rent_property("office-b", "1234567VK4713S0002BB"),
            )
        )

        repository = RetencionObservationRepositoryAdapter(objects=profile.repository)
        annual_source = repository.load_annual_source_observations("115", 2025)
        assert len(annual_source) == 3
        result = aggregate_retenciones_180(annual_source, period=Period.from_year_and_code(2025, "0A"))
        assert result.type2_record_count == 2
        assert result.total_perceptors == 1
        assert result.total_taxable_base == Decimal("500.00")
        assert result.total_retencion == Decimal("95.00")
        assert sorted(row.observations_count for row in result.type2_rows) == [1, 2]


@pytest.mark.parametrize("currency", ["eur", " EUR "])
def test_a_liability_currency_is_normalised_to_the_canonical_euro_code(currency: str) -> None:
    """The canonical currency annotation trims and uppercases before the euro rule reads it."""
    snapshot = SourceLiabilitySnapshot(
        source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
        source_object_id="invoice-currency-case",
        source_revision_id="invoice-revision-1",
        currency=currency,
        liability_base=Decimal("100.00"),
        liability_withholding=Decimal("15.00"),
        liability_settlement=Decimal("85.00"),
    )

    assert snapshot.currency == "EUR"


def test_a_liability_in_another_currency_is_refused() -> None:
    """Spanish withholding is declared and paid in euros; a USD liability never reaches a window."""
    with pytest.raises(ValidationError, match="denominated in EUR"):
        SourceLiabilitySnapshot(
            source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            source_object_id="invoice-usd",
            source_revision_id="invoice-revision-1",
            currency="USD",
            liability_base=Decimal("100.00"),
            liability_withholding=Decimal("15.00"),
            liability_settlement=Decimal("85.00"),
        )
