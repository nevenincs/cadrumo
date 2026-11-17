"""Derive and submit the withholding captures of a persona's rent and professional-fee payments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...application.aggregation.invoice_retencion import InvoiceWithholdingEvidenceRequest
from ...application.aggregation.retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress
from ...application.aggregation.service import PerModeloAggregationCommand
from ...application.aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ...application.modelo.invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ...core.aggregation import RetencionClave, RetencionScheme
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...tests.persona_types import LeasedPremises, LedgerRow, Persona, YearEnvelope
from ...tests.withholding_zero_blocks import zeroed_withholding_blocks
from .persona_operations import run_operation
from .persona_replay_requests import party_name
from .persona_world import PersonaMaterialisationError, PersonaWorld

RENT_WITHHOLDING_MODELO = "115"
"""The modelo whose evidence the retención on a rent payment for leased premises is captured as."""


PROFESSIONAL_WITHHOLDING_MODELO = "111"
"""The modelo whose evidence the retención on a professional's fees is captured as."""


_URBAN_RENT_SCHEME = RetencionScheme("arrendamiento_urbano")


_PROFESSIONAL_SCHEME = RetencionScheme("actividades_profesionales")


#: Modelo 190 clave G, subclave 01: professional income withheld at the general rate of RIRPF art. 95.1.
_PROFESSIONAL_CLAVE = "G"


_PROFESSIONAL_GENERAL_RATE_SUBCLAVE = "01"


_PERCENT = Decimal("100")


_CENTS = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class WithholdingCapture:
    """The withholding one payment's retención is captured as: its modelo, the quarter paid and the evidence."""

    modelo: str
    period: Period
    evidence: InvoiceWithholdingEvidenceRequest
    kind: str
    """``rent`` or ``professional``, naming the capture in a refusal."""


def rent_payments(persona: Persona, premises: LeasedPremises) -> list[LedgerRow]:
    """The received ledger rows from the premises' landlord that carry a retención: one per rent payment."""
    return [
        row
        for row in persona.ledger
        if row.counterparty == premises.landlord
        and row.invoice_kind == "received"
        and row.retencion_amount is not None
        and row.retencion_amount > 0
    ]


def _paid_quarter(paid_on: date) -> Period:
    return Period.from_year_and_code(paid_on.year, f"{(paid_on.month - 1) // 3 + 1}T")


def rent_withholding_capture(
    persona: Persona,
    premises: LeasedPremises,
    row: LedgerRow,
    *,
    envelope: YearEnvelope,
    operation: PinnedAuthorityOperation,
    invoice_id: str,
    payment_event_id: str,
) -> WithholdingCapture:
    """The withholding capture of one rent payment: its invoice, its bank movement and the premises it pays for."""
    if row.taxable_base is None or row.retencion_amount is None or row.retencion_rate is None:
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: a rent payment states its base and retención")
    paid_on = row.operation_date(envelope)
    with validating_governed_facts(operation):
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice_id,
            income_kind=WithholdingIncomeKind.URBAN_RENT,
            scheme=_URBAN_RENT_SCHEME,
            recipient_tax_status=WithholdingRecipientTaxStatus(premises.landlord_tax_status),
            recipient_tax_regime=WithholdingRecipientTaxRegime(premises.landlord_tax_regime),
            payment_event_id=payment_event_id,
            payment_occurred_on=paid_on,
            allocation_id=row.ref,
            allocated_base=row.taxable_base,
            allocated_withholding=row.retencion_amount,
            allocated_settlement=abs(row.amount),
            idempotency_key=f"{persona.id}:{row.ref}",
            modelo_180_property=Modelo180PropertyEvidence(
                property_key=premises.key,
                situation=premises.situation,
                cadastral_reference=premises.cadastral_reference,
                address=Modelo180StructuredAddress.model_validate(dict(premises.address)),
                recipient_province_code=premises.landlord_province,
                modality=premises.modality,
                accrual_year=paid_on.year,
                withholding_percentage=(row.retencion_rate * _PERCENT).quantize(_CENTS),
            ),
        )
    return WithholdingCapture(
        modelo=RENT_WITHHOLDING_MODELO, period=_paid_quarter(paid_on), evidence=evidence, kind="rent"
    )


def professional_fee_payments(persona: Persona) -> list[LedgerRow]:
    """The received ledger rows carrying a retención that pay no leased premises: a professional's fees.

    A received invoice bears a retención the taxpayer practises only as the
    payer of rent or of professional fees; with no employees, the rows that pay
    no landlord are the professional fees.
    """
    landlords = {premises.landlord for premises in persona.leased_premises}
    return [
        row
        for row in persona.ledger
        if row.invoice_kind == "received"
        and row.counterparty not in landlords
        and row.retencion_amount is not None
        and row.retencion_amount > 0
    ]


def professional_withholding_capture(
    persona: Persona,
    row: LedgerRow,
    *,
    envelope: YearEnvelope,
    operation: PinnedAuthorityOperation,
    invoice_id: str,
    payment_event_id: str,
) -> WithholdingCapture:
    """The withholding capture of one professional's invoice paid by the taxpayer, for the Modelo 111 of its quarter.

    The persona's professionals are resident individuals taxed under the IRPF,
    the only recipients whose fees carry the retención of RIRPF art. 95, at its
    general rate; the Modelo 190 annual detail names them under clave G,
    subclave 01. Their domicile province and the payer's Ceuta/Melilla
    determination come from the professional's identity; an identity that
    states neither leaves them absent, so the 190 refuses rather than guesses.
    """
    if (
        row.counterparty is None
        or row.taxable_base is None
        or row.retencion_amount is None
        or row.retencion_rate is None
    ):
        raise PersonaMaterialisationError(f"{persona.id} {row.ref}: a professional fee states its base and retención")
    paid_on = row.operation_date(envelope)
    perceptor = persona.identities.role(row.counterparty)
    with validating_governed_facts(operation):
        evidence = InvoiceWithholdingEvidenceRequest(
            invoice_id=invoice_id,
            income_kind=WithholdingIncomeKind.PROFESSIONAL,
            scheme=_PROFESSIONAL_SCHEME,
            recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
            recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
            payment_event_id=payment_event_id,
            payment_occurred_on=paid_on,
            allocation_id=row.ref,
            allocated_base=row.taxable_base,
            allocated_withholding=row.retencion_amount,
            allocated_settlement=abs(row.amount),
            idempotency_key=f"{persona.id}:{row.ref}",
            modelo_190_detail=WithholdingObservation(
                source_id=invoice_id,
                source_allocation_id=row.ref,
                perceptor_tax_id=perceptor.value,
                perceptor_legal_name=party_name(persona, row.counterparty),
                country_code="ES",
                transaction_date=paid_on,
                clave=RetencionClave.from_registry(_PROFESSIONAL_CLAVE),
                subclave=_PROFESSIONAL_GENERAL_RATE_SUBCLAVE,
                percibido_dinerario=row.taxable_base,
                retencion_practicada=row.retencion_amount,
                **zeroed_withholding_blocks(),
                base_retenciones=row.taxable_base,
                porcentaje_retencion=(row.retencion_rate * _PERCENT).quantize(_CENTS),
                province_code=perceptor.province,
                territorial_deduction_clave=(
                    None if perceptor.ceuta_melilla_deduction is None else int(perceptor.ceuta_melilla_deduction)
                ),
            ),
        )
    return WithholdingCapture(
        modelo=PROFESSIONAL_WITHHOLDING_MODELO, period=_paid_quarter(paid_on), evidence=evidence, kind="professional"
    )


def _capture(persona: Persona, world: PersonaWorld, row: LedgerRow, capture: WithholdingCapture) -> None:
    captured = run_operation(
        world,
        MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=world.profile_id,
            command=PerModeloAggregationCommand(modelo=capture.modelo, period=capture.period),
            evidence=capture.evidence,
        ),
        ModeloInvoiceWithholdingCaptureProjection,
    )
    if captured.outcome != "captured":
        raise PersonaMaterialisationError(
            f"{persona.id} {row.ref}: {capture.kind} withholding refused ({captured.refusal_reason}, "
            f"{captured.refusal_defects})"
        )


def _capture_rent_withholding(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Capture the retención the taxpayer withheld on every rent payment for leased premises, as Modelo 115 evidence."""
    for premises in persona.leased_premises:
        for row in rent_payments(persona, premises):
            capture = rent_withholding_capture(
                persona,
                premises,
                row,
                envelope=world.envelope,
                operation=world.operation,
                invoice_id=invoices[row.ref],
                payment_event_id=transactions[row.ref],
            )
            _capture(persona, world, row, capture)


def _capture_professional_withholding(
    persona: Persona, world: PersonaWorld, *, transactions: Mapping[str, str], invoices: Mapping[str, str]
) -> None:
    """Capture the retención the taxpayer withheld on every professional's invoice, as Modelo 111 evidence."""
    for row in professional_fee_payments(persona):
        capture = professional_withholding_capture(
            persona,
            row,
            envelope=world.envelope,
            operation=world.operation,
            invoice_id=invoices[row.ref],
            payment_event_id=transactions[row.ref],
        )
        _capture(persona, world, row, capture)
