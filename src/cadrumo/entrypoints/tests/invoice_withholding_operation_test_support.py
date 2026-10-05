"""Canonical encrypted-profile seed and readback for invoice withholding conformance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_modelo_ready_profile_record
from cadrumo.application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from cadrumo.application.aggregation.retenciones import RetencionObservation
from cadrumo.application.aggregation.service import PerModeloAggregationCommand
from cadrumo.application.aggregation.withholding_filing_cadence import load_bucket_withholding_filer_cadence
from cadrumo.application.aggregation.withholding_observation_service import WithholdingWindowScope
from cadrumo.application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    derive_withholding_recognition,
)
from cadrumo.application.modelo.invoice_withholding_capture_contracts import ModeloInvoiceWithholdingCaptureRequest
from cadrumo.core.aggregation import BindingSourceKind, RetencionClave, RetencionScheme
from cadrumo.core.period import Period
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.entrypoints.adapter_composition import (
    build_percepcion_observation_ports,
    build_retencion_observation_ports,
    build_withholding_observation_service,
)

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "2T")


@dataclass(frozen=True, slots=True)
class InvoiceWithholdingConformanceSeed:
    """The exact source and request used by the registered executor matrix."""

    request: ModeloInvoiceWithholdingCaptureRequest
    invoice_id: str
    period: Period


@dataclass(frozen=True, slots=True)
class InvoiceWithholdingConformanceReadback:
    """Encrypted store facts after a supervised capture."""

    observations: tuple[RetencionObservation, ...]
    annual_observations: tuple[WithholdingObservation, ...]
    generation: int
    catalogue_contains_invoice: bool


def seed_invoice_withholding_conformance_case(
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
) -> InvoiceWithholdingConformanceSeed:
    """Seed a real received professional invoice and all capture evidence."""
    bucket_id = str(profile_id)
    seed_modelo_ready_profile_record(bucket_id, clock=now(), tax_id="12345678Z")
    with validating_governed_facts(operation):
        issued_on = date(_YEAR, 3, 31)
        paid_on = date(_YEAR, 4, 2)
        subtotal = Decimal("500.00")
        rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), issued_on)
        if rate is None:
            raise AssertionError("published IVA rate is unavailable for the fixture date")
        line = InvoiceLine(
            description="Synthetic professional service",
            quantity=Decimal("1"),
            unit_price=subtotal,
            subtotal=subtotal,
            iva_rate=IvaRate.from_registry("RATE_21"),
            iva_amount=subtotal * rate,
        )
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.RECEIVED,
                "bucket_id": bucket_id,
                "invoice_number": "CONFORMANCE-WITHHOLDING-2025-001",
                "issued_at": issued_on,
                "counterparty_name": "Synthetic Professional",
                "counterparty_tax_id": "11111111H",
                "counterparty_country": "ES",
                "base_total": subtotal,
                "iva_total": line.iva_amount,
                "grand_total": subtotal + line.iva_amount,
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
                "iva_category": IvaCategory("domestic_general"),
                "retention_rate": Decimal("0.19"),
                "retention_amount": Decimal("95.00"),
            }
        )
        detail = WithholdingObservation(
            source_id=invoice.invoice_id,
            perceptor_tax_id=invoice.counterparty_tax_id or "",
            perceptor_legal_name=invoice.counterparty_name,
            transaction_date=paid_on,
            clave=RetencionClave.from_registry("G"),
            percibido_dinerario=subtotal,
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
            base_retenciones=subtotal,
            porcentaje_retencion=Decimal("19"),
        )
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice.invoice_id,
            income_kind=WithholdingIncomeKind.PROFESSIONAL,
            scheme=RetencionScheme("actividades_profesionales"),
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            payment_event_id="conformance-professional-payment-2025-04",
            payment_occurred_on=paid_on,
            allocation_id="conformance-professional-allocation-2025-04",
            allocated_base=subtotal,
            allocated_withholding=Decimal("95.00"),
            allocated_settlement=Decimal("510.00"),
            idempotency_key="conformance-professional-capture-2025-04",
            modelo_190_detail=detail,
        )
        request = ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=profile_id,
            command=PerModeloAggregationCommand(modelo="111", period=_PERIOD),
            evidence=evidence,
        )
    InvoiceCatalogueRepository(bucket_id=bucket_id).save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))
    return InvoiceWithholdingConformanceSeed(request=request, invoice_id=str(invoice.invoice_id), period=_PERIOD)


def read_invoice_withholding_conformance_case(
    profile_id: UUID,
    seed: InvoiceWithholdingConformanceSeed,
) -> InvoiceWithholdingConformanceReadback:
    """Read the committed invoice, per-perceptor rows and window generation."""
    bucket_id = str(profile_id)
    observations = build_retencion_observation_ports(bucket_id=bucket_id).repository.load_observations(
        "111", seed.period
    )
    annual_observations = build_percepcion_observation_ports(bucket_id=bucket_id).repository.load_observations(
        "111", seed.period
    )
    state = build_withholding_observation_service(bucket_id=bucket_id).read_window(
        WithholdingWindowScope(modelo="111", period=seed.period)
    )
    catalogue = InvoiceCatalogueRepository(bucket_id=bucket_id).load()
    return InvoiceWithholdingConformanceReadback(
        observations=tuple(observations),
        annual_observations=tuple(annual_observations),
        generation=state.generation,
        catalogue_contains_invoice=seed.invoice_id in catalogue.invoices,
    )


def assert_invoice_withholding_conformance_write(
    readback: InvoiceWithholdingConformanceReadback,
    seed: InvoiceWithholdingConformanceSeed,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
) -> None:
    """Compare both encrypted rows with a fresh canonical capture derivation."""
    bucket_id = str(profile_id)
    catalogue, revision_id = InvoiceCatalogueRepository(bucket_id=bucket_id).load_revisioned()
    invoice = catalogue.invoices[seed.invoice_id]
    with validating_governed_facts(operation):
        evidence = seed.request.evidence.to_domain()
        cadence = load_bucket_withholding_filer_cadence(
            bucket_id=bucket_id,
            filing_year=seed.period.filing_year,
            operation=operation,
        )
        capture = build_invoice_withholding_capture(
            invoice,
            catalogue_revision_id=revision_id,
            request=evidence,
            applicable_year=seed.period.filing_year,
            cadence=cadence,
        )
        command = capture.command
        recognition = derive_withholding_recognition(
            command.recognition_evidence,
            modelo=capture.scope.modelo,
        )
        expected_retencion = RetencionObservation(
            source_kind=command.source_kind,
            source_object_id=command.source_object_id,
            perceptor_nif=command.perceptor_nif,
            perceptor_name=command.perceptor_name,
            scheme=command.scheme,
            taxable_base=command.taxable_base,
            retencion_amount=command.retencion_amount,
            accrued_on=recognition.recognized_on.isoformat(),
            modelo_180_property=command.modelo_180_property,
        )
        detail = command.modelo_190_detail
        if detail is None:
            raise AssertionError("professional capture lacks its required annual detail")
        expected_annual = detail.model_copy(update={"source_allocation_id": command.allocation_id})
    if (
        readback.generation != 1
        or not readback.catalogue_contains_invoice
        or capture.scope.period != seed.period
        or command.source_kind is not BindingSourceKind.PAYABLE_INVOICE
        or readback.observations != (expected_retencion,)
        or readback.annual_observations != (expected_annual,)
    ):
        raise AssertionError("invoice withholding capture differs from its canonical source evidence")
