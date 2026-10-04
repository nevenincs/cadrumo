"""Route a received invoice's retención into the one per-perceptor store.

Retención arithmetic is identical on both kinds of invoice and means opposite
things. On an ISSUED invoice the payer withholds from what they owe the
taxpayer and remits it on the taxpayer's account: the taxpayer is the
*retenido* and the amount is a CREDIT against the pago fraccionado (RIRPF
art. 110.3.a). On a RECEIVED invoice from a resident professional the taxpayer
is the obligated *retenedor* and the amount is a LIABILITY settled to AEAT
through Modelo 111 and its annual summary.

Those two destinations already exist and neither is here. The credit reaches
the M130/M100 retenciones casilla through the renta income ledger. The
liability's canonical home is the per-perceptor retención store behind the
``retenciones_aggregation`` binding family, whose committed M111 bindings
already read it. This module translates a received invoice into the shared
withholding producer's capture command and nothing else, so a received invoice
becomes one more observation in the one store rather than a second retención
path with its own totals to reconcile.

**The scheme is not inferred.** Which registry-owned retención scheme a payment
falls under is a legal fact about the perceptor's activity, not a property of
the invoice. An invoice record carries no field that settles it. So the caller
declares it, and this module refuses to guess: choosing a scheme here would
file a figure under a clave the taxpayer never asserted.

The production caller is the ``modelo aggregate`` CLI: an operator (or the LLM
operator on their behalf) declares one allocation via
``--received-invoice-retencion``, which the CLI parses into an
:class:`InvoiceWithholdingEvidenceRequest` and hands to
:func:`build_invoice_withholding_capture`. That capture routes the invoice
through :func:`invoice_retencion_liability_defects`, the canonical defect sweep, so a
refused invoice reports every defect it carries rather than the first one
found. The shared withholding producer owns the write, so this module never
persists anything itself.

See Also:
    :mod:`~.retenciones`
        The observation type, the aggregators, and the source-kind taxonomy.
    :mod:`~.withholding_producer`
        The shared producer that owns every write into the per-perceptor store,
        committing this module's capture command as one atomic generation.
    :class:`~cadrumo.domain.iva.components.IvaRetencionRole`
        The declared per-(category, kind) role this module routes on, rather
        than re-deriving the direction from the invoice kind.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import BindingSourceKind, RetencionScheme
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.i18n.render import tr as render_tr
from ...core.identity.hex_ids import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.iva.components import category_components, registry_retencion_role_token
from .retenciones import Modelo180PropertyEvidence, Modelo193PendingPaymentEvidence
from .withholding_filing_cadence import WithholdingFilerCadence, quarterly_withholding_capture_period
from .withholding_observation_service import (
    SourceLiabilitySnapshot,
    WithholdingMutationMode,
    WithholdingWindowBaseline,
    WithholdingWindowScope,
)
from .withholding_producer import WithholdingEvidenceCaptureCommand
from .withholding_recognition import (
    WithholdingDatedEvent,
    WithholdingIncomeKind,
    WithholdingOperationKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
    WithholdingRecognitionEvidence,
    derive_withholding_recognition,
)

if TYPE_CHECKING:
    from ...domain.invoices.models import Invoice

_SPANISH_COUNTRY_CODE: Final[str] = "ES"


class InvoiceRetencionProjectionDefect(StrEnum):
    """Why one invoice's retención did not become a store observation.

    Every member EXCLUDES the invoice from the retenciones store and is
    reported rather than dropped. None of them is a refusal to record the
    invoice itself -- the record stays in the catalogue and stays editable.
    """

    NOT_A_RETENEDOR_LIABILITY = "not_a_retenedor_liability"
    """The Axis-A role for this invoice is not a liability the taxpayer owes.

    Most often the invoice is issued, so its retención is the taxpayer's
    CREDIT: routing it here would declare them retenedor for money withheld
    FROM them, inverting the direction of a tax liability. It is not a missing
    figure; it belongs to the income side and is already carried there. The
    same member covers a (category, kind) pair whose role is ``NONE`` or
    ``UNKNOWN`` -- neither is a liability this store may assert.
    """

    IVA_TREATMENT_UNDECLARED = "iva_treatment_undeclared"
    """No IVA category is declared, so the retención role cannot be read.

    The role is per ``(category, kind)`` pair, so without a category there is
    no row to consult and the direction of the amount is unknown. Guessing it
    from the kind alone is exactly the re-derivation this module refuses.
    """

    NO_RETENCION_DECLARED = "no_retencion_declared"
    """The invoice declares no withheld amount, or declares it as zero.

    Nothing to route. Most received invoices are in this state legitimately.
    """

    NON_RESIDENT_SUPPLIER = "non_resident_supplier"
    """The supplier is not Spanish-resident, so Modelo 111 is the wrong home.

    The retenedor obligation on payments to non-residents runs through the IRNR
    surface, not the IRPF per-perceptor family this store feeds. Excluding is
    the conservative direction: it surfaces the invoice for the operator rather
    than filing a figure under a modelo that does not govern it.
    """

    FX_UNRESOLVED = "fx_unresolved"
    """A non-euro invoice carries no resolved conversion rate.

    The euro base and retención are unknown, and the store holds euro figures.
    """

    MISSING_COUNTERPARTY_TAX_ID = "missing_counterparty_tax_id"
    """A factura simplificada declared a retención but names no perceptor.

    Modelo 111 requires the perceptor's NIF; an invoice may legitimately carry
    no ``counterparty_tax_id`` (RD 1619/2012 art. 6.1.d), but a supplier
    withholding tax is one of the cases that article makes the tax id
    mandatory for regardless, so this exclusion should be rare in practice.
    """


_DEFECT_REASON_LOCALE_KEYS: Final[dict[InvoiceRetencionProjectionDefect, str]] = {
    InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY: (
        "aggregation.invoice_retencion.defects.not_a_retenedor_liability"
    ),
    InvoiceRetencionProjectionDefect.IVA_TREATMENT_UNDECLARED: (
        "aggregation.invoice_retencion.defects.iva_treatment_undeclared"
    ),
    InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED: (
        "aggregation.invoice_retencion.defects.no_retencion_declared"
    ),
    InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER: (
        "aggregation.invoice_retencion.defects.non_resident_supplier"
    ),
    InvoiceRetencionProjectionDefect.FX_UNRESOLVED: "aggregation.invoice_retencion.defects.fx_unresolved",
    InvoiceRetencionProjectionDefect.MISSING_COUNTERPARTY_TAX_ID: (
        "aggregation.invoice_retencion.defects.missing_counterparty_tax_id"
    ),
}
"""The operator-facing explanation of each defect, one canonical key per member."""


class InvoiceWithholdingEvidenceError(CadrumoError):
    """Payload-free refusal while making invoice evidence capture-ready."""

    def __init__(self, refusal_code: str) -> None:
        """Build a refusal that carries only its stable reason token."""
        super().__init__(f"invoice withholding evidence refused: {refusal_code}")
        self.refusal_code = refusal_code


class InvoiceWithholdingDefectsError(InvoiceWithholdingEvidenceError):
    """Refusal naming every defect that keeps an invoice's retención out of capture.

    ``refusal_code`` joins every defect token in the projection's order, so a
    one-defect refusal keeps the exact code it always carried and a transport
    that shows only the code still shows every defect. The context carries
    each defect's explanation in the operator's language beside the registered
    refusal message; it holds no invoice figure or identity.
    """

    def __init__(self, defects: tuple[InvoiceRetencionProjectionDefect, ...]) -> None:
        """Build the refusal from the projection's complete defect tuple."""
        super().__init__(",".join(defect.value for defect in defects))
        self._defects = defects
        reasons: dict[str, object] = {
            "defect_reasons": " ".join(render_tr(_DEFECT_REASON_LOCALE_KEYS[defect]) for defect in defects),
        }
        self.context = reasons

    @property
    def defects(self) -> tuple[InvoiceRetencionProjectionDefect, ...]:
        """Every defect the projection found, in its sweep order."""
        return self._defects


class InvoiceWithholdingEvidenceRequest(BaseModel):
    """CLI-safe recognition and settlement evidence for one invoice allocation.

    The invoice catalogue supplies the source revision, liability limits,
    currency and recipient identity.  This request holds only facts that the
    catalogue cannot establish: the recipient's supported tax status and
    underlying payment/satisfaction or exigibility evidence.  It intentionally
    has no recognition date or liability-total field.
    """

    model_config = _STRICT_FROZEN

    invoice_id: InvoiceId
    income_kind: WithholdingIncomeKind
    scheme: RetencionScheme
    recipient_tax_status: WithholdingRecipientTaxStatus
    recipient_tax_regime: WithholdingRecipientTaxRegime
    payment_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    payment_occurred_on: date | None = None
    exigibility_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    exigibility_occurred_on: date | None = None
    allocation_id: str
    allocated_base: Decimal
    allocated_withholding: Decimal
    allocated_settlement: Decimal
    idempotency_key: str
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND
    baseline: WithholdingWindowBaseline | None = None
    reason: str | None = None
    supersedes_generation_id: str | None = None
    modelo_180_property: Modelo180PropertyEvidence | None = None
    modelo_190_detail: WithholdingObservation | None = None
    modelo_193_pending_payment: Modelo193PendingPaymentEvidence | None = None

    @model_validator(mode="after")
    def _dated_evidence_is_complete(self) -> Self:
        """Keep each underlying event atomic at the public transport edge."""
        if (self.payment_event_id is None) != (self.payment_occurred_on is None):
            raise ValueError("payment evidence requires both event id and date")
        if (self.exigibility_event_id is None) != (self.exigibility_occurred_on is None):
            raise ValueError("exigibility evidence requires both event id and date")
        return self


class InvoiceWithholdingCapture(BaseModel):
    """Canonical invoice-derived producer command and its consistent read revision."""

    model_config = _STRICT_FROZEN

    command: WithholdingEvidenceCaptureCommand
    scope: WithholdingWindowScope
    catalogue_read_revision_id: str


def _validate_invoice_capture_coordinates(
    invoice: Invoice,
    *,
    request: InvoiceWithholdingEvidenceRequest,
    applicable_year: int,
    cadence: WithholdingFilerCadence,
) -> None:
    if request.invoice_id != invoice.invoice_id:
        raise InvoiceWithholdingEvidenceError("invoice_identity_mismatch")
    if cadence.filing_year != applicable_year:
        raise InvoiceWithholdingEvidenceError("filer_cadence_year_mismatch")


def _invoice_withholding_liability(
    invoice: Invoice,
) -> tuple[Decimal, Decimal, Decimal, str]:
    defects = invoice_retencion_liability_defects(invoice)
    if defects:
        raise InvoiceWithholdingDefectsError(defects)
    base = invoice.base_total_eur
    withholding = invoice.retention_amount_eur
    total = invoice.grand_total_eur
    if base is None or withholding is None or total is None:
        raise InvoiceWithholdingEvidenceError("invoice_eur_liability_unavailable")
    settlement = total - withholding
    if settlement < Decimal("0"):
        raise InvoiceWithholdingEvidenceError("contradictory_invoice_settlement")
    if invoice.counterparty_tax_id is None:
        raise InvoiceWithholdingEvidenceError("missing_counterparty_tax_id")
    return base, withholding, settlement, invoice.counterparty_tax_id


def _invoice_capture_recognition_evidence(
    request: InvoiceWithholdingEvidenceRequest,
    *,
    applicable_year: int,
) -> WithholdingRecognitionEvidence:
    return WithholdingRecognitionEvidence(
        applicable_year=applicable_year,
        recipient_tax_status=request.recipient_tax_status,
        recipient_tax_regime=request.recipient_tax_regime,
        income_kind=request.income_kind,
        operation_kind=WithholdingOperationKind.ORDINARY,
        payment_or_satisfaction=(
            WithholdingDatedEvent(
                event_id=request.payment_event_id,
                occurred_on=request.payment_occurred_on,
            )
            if request.payment_event_id is not None and request.payment_occurred_on is not None
            else None
        ),
        exigibility=(
            WithholdingDatedEvent(
                event_id=request.exigibility_event_id,
                occurred_on=request.exigibility_occurred_on,
            )
            if request.exigibility_event_id is not None and request.exigibility_occurred_on is not None
            else None
        ),
    )


def build_invoice_withholding_capture(
    invoice: Invoice,
    *,
    catalogue_revision_id: str,
    request: InvoiceWithholdingEvidenceRequest,
    applicable_year: int,
    cadence: WithholdingFilerCadence,
) -> InvoiceWithholdingCapture:
    """Derive one producer command from the current canonical invoice revision.

    This is deliberately the sole invoice-to-withholding translation.  It
    refuses missing catalogue facts rather than accepting caller substitutes
    for a liability limit, source revision, recognition coordinate, or
    recipient identity.  ``cadence`` is the filer's canonical schedule for
    ``applicable_year``; a recognition quarter it does not assign is refused.

    The canonical defect sweep reports every reason an invoice cannot supply
    a liability before its euro figures become a capture command.
    """
    _validate_invoice_capture_coordinates(
        invoice,
        request=request,
        applicable_year=applicable_year,
        cadence=cadence,
    )
    base, withholding, settlement, perceptor_nif = _invoice_withholding_liability(invoice)
    evidence = _invoice_capture_recognition_evidence(request, applicable_year=applicable_year)
    # The catalogue revision proves this invoice was read consistently from the
    # encrypted singleton.  It is deliberately not the source revision: that
    # singleton changes for unrelated invoices, and using it as the allocation
    # identity would strand a later payment behind a false liability conflict.
    source_revision_id = content_hash_hex(
        {
            "invoice_id": invoice.invoice_id,
            "currency": invoice.currency,
            "base": str(base),
            "withholding": str(withholding),
            "settlement": str(settlement),
            "perceptor_nif": perceptor_nif,
        }
    )
    command = WithholdingEvidenceCaptureCommand(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id=invoice.invoice_id,
        source_revision_id=source_revision_id,
        allocation_id=request.allocation_id,
        perceptor_nif=perceptor_nif,
        perceptor_name=invoice.counterparty_name,
        scheme=request.scheme,
        taxable_base=request.allocated_base,
        retencion_amount=request.allocated_withholding,
        settlement_amount=request.allocated_settlement,
        liability_snapshot=SourceLiabilitySnapshot(
            source_kind=BindingSourceKind.PAYABLE_INVOICE.value,
            source_object_id=invoice.invoice_id,
            source_revision_id=source_revision_id,
            liability_base=base,
            liability_withholding=withholding,
            liability_settlement=settlement,
        ),
        recognition_evidence=evidence,
        mode=request.mode,
        idempotency_key=request.idempotency_key,
        baseline=request.baseline,
        reason=request.reason,
        supersedes_generation_id=request.supersedes_generation_id,
        modelo_180_property=request.modelo_180_property,
        modelo_190_detail=request.modelo_190_detail,
        modelo_193_pending_payment=request.modelo_193_pending_payment,
    )
    modelo = _modelo_for_income(request.income_kind)
    recognition = derive_withholding_recognition(evidence, modelo=modelo)
    return InvoiceWithholdingCapture(
        command=command,
        scope=WithholdingWindowScope(
            modelo=modelo,
            period=quarterly_withholding_capture_period(
                cadence,
                modelo=modelo,
                recognized_on=recognition.recognized_on,
            ),
        ),
        catalogue_read_revision_id=catalogue_revision_id,
    )


def _modelo_for_income(income_kind: WithholdingIncomeKind) -> str:
    if income_kind in {WithholdingIncomeKind.WORK, WithholdingIncomeKind.PROFESSIONAL}:
        return "111"
    if income_kind is WithholdingIncomeKind.URBAN_RENT:
        return "115"
    if income_kind is WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL:
        return "123"
    raise InvoiceWithholdingEvidenceError("unsupported_income_projection")


def invoice_retencion_liability_defects(invoice: Invoice) -> tuple[InvoiceRetencionProjectionDefect, ...]:
    """Return every reason the invoice carries no routable retenedor-liability retención.

    An empty tuple is the positive answer: this received invoice declares a
    retención the taxpayer owes as retenedor and that the per-perceptor store
    should therefore hold. Public because it is the ONE predicate for that
    question -- a later filing-grade gate compares the ledger against the store
    and must ask it exactly as the routing does, not with a second copy free to
    drift from the Axis-A role table.

    Accumulating rather than short-circuiting, so an operator fixing a record
    sees everything wrong with it in one pass.

    The direction test reads the Axis-A ``retencion_role`` rather than
    re-deriving it from the invoice kind. The role is declared per
    ``(category, kind)`` pair and validated against that kind at authoring
    time, so consulting it keeps one definition of whose money a retención is;
    a local ``kind is RECEIVED`` test would be a second, unvalidated copy of
    the same fact, free to drift from the table the rest of the engine reads.
    """
    defects: list[InvoiceRetencionProjectionDefect] = []
    if invoice.iva_category is None:
        defects.append(InvoiceRetencionProjectionDefect.IVA_TREATMENT_UNDECLARED)
    elif category_components(invoice.iva_category, invoice.kind).retencion_role != registry_retencion_role_token(
        "taxpayer_liability",
    ):
        defects.append(InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY)
    if invoice.retention_amount is None or invoice.retention_amount == Decimal("0"):
        defects.append(InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED)
    if invoice.counterparty_country != _SPANISH_COUNTRY_CODE:
        defects.append(InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER)
    if invoice.currency != DEFAULT_CURRENCY and invoice.fx_rate is None:
        defects.append(InvoiceRetencionProjectionDefect.FX_UNRESOLVED)
    if invoice.counterparty_tax_id is None:
        defects.append(InvoiceRetencionProjectionDefect.MISSING_COUNTERPARTY_TAX_ID)
    return tuple(defects)


__all__ = [
    "InvoiceRetencionProjectionDefect",
    "invoice_retencion_liability_defects",
]
