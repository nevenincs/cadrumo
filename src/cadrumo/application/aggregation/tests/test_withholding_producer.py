"""Operational producer-to-Modelo-111 proof over encrypted withholding storage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.percepciones_observations import PercepcionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.retencion_observations import RetencionObservationRepositoryAdapter
from cadrumo.adapters.persistence.profile.withholding_observation_workflow import WithholdingObservationWorkflowAdapter
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from cadrumo.application.aggregation.retencion_observations_repository import RetencionObservationPorts
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.withholding_observation_service import (
    ABSENT_WITHHOLDING_GENERATION_ID,
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
    WithholdingRecognitionEvidence,
)
from cadrumo.core.aggregation import BindingSourceKind, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFESSIONAL_SCHEME = RetencionScheme("actividades_profesionales")


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
) -> WithholdingEvidenceCaptureCommand:
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
        recognition_evidence=WithholdingRecognitionEvidence(
            applicable_year=2025,
            recipient_tax_status=recipient_status,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            income_kind=income_kind,
            operation_kind=WithholdingOperationKind.ORDINARY,
            payment_or_satisfaction=WithholdingDatedEvent(event_id=payment_id, occurred_on=paid_on),
        ),
        idempotency_key=f"capture-{allocation_id}",
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
        assert len(state.entries) == 2
        persisted = RetencionObservationRepositoryAdapter(objects=profile.repository).load_observations(
            "111", Period.from_year_and_code(2025, "2T")
        )
        assert len(persisted) == 2
        assert {row.accrued_on for row in persisted} == {"2025-04-02", "2025-06-30"}

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


def test_invalid_recognition_refuses_before_any_encrypted_projection_write(tmp_path: Path) -> None:
    """Unsupported recipient evidence cannot create a partial withholding window."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        producer, service = _producer_for(profile.repository)
        command = _command(recipient_status=WithholdingRecipientTaxStatus.NONRESIDENT)

        with pytest.raises(ValueError, match="irnr_unsupported"):
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
