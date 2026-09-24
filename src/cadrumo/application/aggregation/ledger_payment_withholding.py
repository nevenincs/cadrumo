"""Capture payroll and movable-capital withholding anchored to the ledger payment.

Two resident-IRPF income kinds have no invoice behind them: the work income an
employer pays (LIRPF art. 99; RIRPF art. 76), settled through Modelo 111 with
its Modelo 190 annual summary, and the ordinary movable-capital income a payer
satisfies (interest, dividends and other capital income), settled through
Modelo 123 with its Modelo 193 annual summary. For both, the evidence this
producer accepts is the ledger transaction that paid the recipient: its booked
date is the dated payment event, and the transaction is the source whose
identity and revision the allocation carries.

A bank movement cannot state the terms behind it. The gross income, the IRPF
withheld and the recipient's tax status are legal facts of the relationship,
so the caller declares them and this module checks them against what the
ledger proves: an outgoing, euro-denominated payment whose paid magnitude
equals the declared net settlement.

The two kinds differ only where the recognition rule differs. Work income is
recognised when paid, so the payment alone dates it. Ordinary movable-capital
income is recognised when it becomes exigible, or when paid if payment comes
first (RIRPF art. 94.1), so the request must also carry the exigibility event;
:mod:`~.withholding_recognition` derives the earlier date. A capital payment
booked in a later year than the income was recognised means the income was
still unpaid at the close of that year. The only such case the shared producer
supports is the Modelo 193 pending-payment disclosure, so that payment refuses
unless the request carries that evidence.

The declared net settlement is bounded above by gross minus withholding rather
than required to equal it. A payroll net is the gross remuneration less the
IRPF withholding *and* the employee's own deductions, such as the Social
Security contribution withheld by the employer (LIRPF art. 19.2.a), union dues
or a court-ordered garnishment. Those deductions do not change the withholding
base, and none of them is visible on the payment, so an equality rule would
refuse every ordinary payslip while a looser rule would invent one. The
recognition rule does not define a net-to-gross relationship for capital
income, so capital keeps the same upper bound rather than an equality this
module cannot ground.

Capturing capital evidence stores it in the Modelo 123 window only. It does
not make that window calculable: the Modelo 123 "Número de rentas" count has
no official definition, and the calculation path refuses a window that holds
captured evidence.

See Also:
    :mod:`~.withholding_producer`
        The shared producer command this module builds, and the only path that
        mutates withholding evidence.
    :mod:`~.withholding_recognition`
        The recognition derivation whose year and recipient support this
        module defers to rather than restating.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.aggregation import BindingSourceKind, RetencionScheme
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.identity.tax_id import TaxIdIdentityToken
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from .retenciones import Modelo193PendingPaymentEvidence
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
    WithholdingRecognitionError,
    WithholdingRecognitionEvidence,
    derive_withholding_recognition,
)

if TYPE_CHECKING:
    from ...domain.transactions.models import Transaction, TransactionCatalogue

# The periodic modelo each ledger-paid income kind settles through. The shared
# producer re-derives it from the scheme at capture and refuses a disagreement.
_PERIODIC_MODELO: dict[WithholdingIncomeKind, str] = {
    WithholdingIncomeKind.WORK: "111",
    WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL: "123",
}


class LedgerPaymentWithholdingEvidenceError(CadrumoError):
    """Payload-free refusal while making a ledger payment capture-ready."""

    def __init__(self, refusal_code: str) -> None:
        """Build a refusal that carries only its stable reason token."""
        super().__init__(f"ledger payment withholding evidence refused: {refusal_code}")
        self.refusal_code = refusal_code


class LedgerPaymentWithholdingEvidenceRequest(BaseModel):
    """CLI-safe terms for the one allocation a ledger payment settles.

    The ledger supplies the payment date, currency, paid magnitude and source
    identity. This request holds only what a payment cannot establish: the
    income terms, the recipient's tax status and the income-kind evidence.
    Work income carries the Modelo 190 annual detail that names the
    perceptor. Ordinary movable-capital income names the perceptor directly,
    carries its exigibility event, and may carry the Modelo 193
    pending-payment evidence. It deliberately has no payment-date,
    recognition-date or period field.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    income_kind: WithholdingIncomeKind = WithholdingIncomeKind.WORK
    scheme: RetencionScheme
    recipient_tax_status: WithholdingRecipientTaxStatus
    recipient_tax_regime: WithholdingRecipientTaxRegime
    payment_event_id: str = Field(min_length=1, max_length=128)
    allocation_id: str = Field(min_length=1, max_length=128)
    gross_base: Decimal = Field(ge=Decimal("0"))
    withholding_amount: Decimal = Field(ge=Decimal("0"))
    net_settlement: Decimal = Field(ge=Decimal("0"))
    idempotency_key: str
    mode: WithholdingMutationMode = WithholdingMutationMode.APPEND
    baseline: WithholdingWindowBaseline | None = None
    reason: str | None = None
    supersedes_generation_id: str | None = None
    modelo_190_detail: WithholdingObservation | None = None
    perceptor_nif: TaxIdIdentityToken | None = Field(default=None, min_length=1, max_length=16)
    perceptor_name: str | None = Field(default=None, max_length=200)
    exigibility_event_id: str | None = Field(default=None, min_length=1, max_length=128)
    exigibility_occurred_on: date | None = None
    modelo_193_pending_payment: Modelo193PendingPaymentEvidence | None = None

    @field_validator("income_kind")
    @classmethod
    def _only_ledger_paid_income(cls, value: WithholdingIncomeKind) -> WithholdingIncomeKind:
        """Keep other income kinds on the producers whose evidence proves them."""
        if value not in _PERIODIC_MODELO:
            raise ValueError("ledger payment withholding capture accepts work or ordinary movable capital income only")
        return value

    @model_validator(mode="after")
    def _evidence_matches_income_kind(self) -> Self:
        """Require each kind's own evidence and forbid the other kind's."""
        if (self.exigibility_event_id is None) != (self.exigibility_occurred_on is None):
            raise ValueError("exigibility evidence requires both event id and date")
        if self.income_kind is WithholdingIncomeKind.WORK:
            if self.modelo_190_detail is None:
                raise ValueError("work income requires Modelo 190 annual detail")
            if self.perceptor_nif is not None or self.perceptor_name is not None:
                raise ValueError("work income takes its perceptor from the Modelo 190 annual detail")
            if self.exigibility_event_id is not None:
                raise ValueError("work income is recognised when paid and takes no exigibility evidence")
            if self.modelo_193_pending_payment is not None:
                raise ValueError("only ordinary movable capital can carry Modelo 193 pending-payment evidence")
            return self
        if self.modelo_190_detail is not None:
            raise ValueError("ordinary movable capital income takes no Modelo 190 annual detail")
        if self.perceptor_nif is None:
            raise ValueError("ordinary movable capital income requires the perceptor NIF")
        if self.perceptor_name is None or not self.perceptor_name.strip():
            raise ValueError("ordinary movable capital income requires the perceptor name")
        if self.exigibility_event_id is None:
            raise ValueError("ordinary movable capital income requires exigibility evidence")
        return self


class LedgerPaymentWithholdingCapture(BaseModel):
    """Canonical ledger-derived producer command and its consistent read revision."""

    model_config = _STRICT_FROZEN

    command: WithholdingEvidenceCaptureCommand
    scope: WithholdingWindowScope
    catalogue_read_revision_id: str


def resolve_ledger_payment_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    """Return the addressed transaction, refusing an id the catalogue does not hold."""
    transaction = catalogue.get(transaction_id)
    if transaction is None:
        raise LedgerPaymentWithholdingEvidenceError("transaction_not_found")
    return transaction


def build_ledger_payment_withholding_capture(
    transaction: Transaction,
    *,
    catalogue_revision_id: str,
    request: LedgerPaymentWithholdingEvidenceRequest,
    applicable_year: int,
    cadence: WithholdingFilerCadence,
) -> LedgerPaymentWithholdingCapture:
    """Derive one work or capital producer command from the paying ledger transaction.

    This is the sole ledger-payment-to-withholding translation. Every payment,
    amount, recipient and timing check runs before a command exists, so a
    refusal can never leave a partial capture behind. The scheme-to-income
    table and the Modelo 193 detail agreement stay with the shared producer.
    ``cadence`` is the filer's canonical schedule for ``applicable_year``; a
    recognition quarter it does not assign is refused.
    """
    if request.transaction_id != transaction.transaction_id:
        raise LedgerPaymentWithholdingEvidenceError("transaction_identity_mismatch")
    if cadence.filing_year != applicable_year:
        raise LedgerPaymentWithholdingEvidenceError("filer_cadence_year_mismatch")
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise LedgerPaymentWithholdingEvidenceError("transaction_not_active")
    if transaction.direction is not TransactionDirection.OUTGOING:
        raise LedgerPaymentWithholdingEvidenceError("transaction_not_outgoing_payment")
    if transaction.raw.currency != DEFAULT_CURRENCY:
        if transaction.value_in_eur is None:
            raise LedgerPaymentWithholdingEvidenceError("payment_eur_amount_unavailable")
        raise LedgerPaymentWithholdingEvidenceError("payment_currency_not_eur")
    if request.withholding_amount > request.gross_base:
        raise LedgerPaymentWithholdingEvidenceError("withholding_exceeds_gross_base")
    if request.net_settlement > request.gross_base - request.withholding_amount:
        raise LedgerPaymentWithholdingEvidenceError("settlement_exceeds_gross_less_withholding")
    # The stored amount is a non-negative magnitude; direction carries the flow.
    if transaction.raw.amount != request.net_settlement:
        raise LedgerPaymentWithholdingEvidenceError("paid_amount_settlement_mismatch")
    if request.recipient_tax_status is WithholdingRecipientTaxStatus.NONRESIDENT:
        raise LedgerPaymentWithholdingEvidenceError("recipient_nonresident")
    if request.recipient_tax_status is WithholdingRecipientTaxStatus.UNKNOWN:
        raise LedgerPaymentWithholdingEvidenceError("recipient_residence_unknown")

    modelo = _PERIODIC_MODELO[request.income_kind]
    payment_on = transaction.raw.booked_date
    evidence = WithholdingRecognitionEvidence(
        applicable_year=applicable_year,
        recipient_tax_status=request.recipient_tax_status,
        recipient_tax_regime=request.recipient_tax_regime,
        income_kind=request.income_kind,
        operation_kind=WithholdingOperationKind.ORDINARY,
        payment_or_satisfaction=WithholdingDatedEvent(event_id=request.payment_event_id, occurred_on=payment_on),
        exigibility=_exigibility_event(request),
    )
    try:
        recognition = derive_withholding_recognition(evidence, modelo=modelo)
    except WithholdingRecognitionError as exc:
        raise LedgerPaymentWithholdingEvidenceError(exc.refusal_code) from exc
    recognized_on = recognition.recognized_on
    if recognized_on.year != applicable_year:
        raise LedgerPaymentWithholdingEvidenceError(
            "payment_outside_applicable_year"
            if request.income_kind is WithholdingIncomeKind.WORK
            else "recognition_outside_applicable_year"
        )
    if payment_on.year > recognized_on.year and request.modelo_193_pending_payment is None:
        raise LedgerPaymentWithholdingEvidenceError("capital_paid_after_accrual_year_without_pending_evidence")
    period = quarterly_withholding_capture_period(cadence, modelo=modelo, recognized_on=recognized_on)

    perceptor_nif, perceptor_name = _perceptor(request)
    # The bucket-wide catalogue revision changes whenever any other row is
    # written, so it proves only a consistent read. The source revision binds
    # the facts this liability rests on, keeping replay and later corrections
    # addressed to the same payment.
    source_facts: dict[str, str] = {
        "transaction_id": transaction.transaction_id,
        "currency": transaction.raw.currency,
        "paid_amount": str(transaction.raw.amount),
        "paid_on": payment_on.isoformat(),
        "gross_base": str(request.gross_base),
        "withholding": str(request.withholding_amount),
        "settlement": str(request.net_settlement),
        "perceptor_nif": perceptor_nif,
    }
    if evidence.exigibility is not None:
        source_facts |= {
            "income_kind": request.income_kind.value,
            "exigibility_event_id": evidence.exigibility.event_id,
            "exigible_on": evidence.exigibility.occurred_on.isoformat(),
        }
    source_revision_id = content_hash_hex(source_facts)
    command = WithholdingEvidenceCaptureCommand(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=transaction.transaction_id,
        source_revision_id=source_revision_id,
        allocation_id=request.allocation_id,
        perceptor_nif=perceptor_nif,
        perceptor_name=perceptor_name,
        scheme=request.scheme,
        taxable_base=request.gross_base,
        retencion_amount=request.withholding_amount,
        settlement_amount=request.net_settlement,
        liability_snapshot=SourceLiabilitySnapshot(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION.value,
            source_object_id=transaction.transaction_id,
            source_revision_id=source_revision_id,
            liability_base=request.gross_base,
            liability_withholding=request.withholding_amount,
            liability_settlement=request.net_settlement,
        ),
        recognition_evidence=evidence,
        mode=request.mode,
        idempotency_key=request.idempotency_key,
        baseline=request.baseline,
        reason=request.reason,
        supersedes_generation_id=request.supersedes_generation_id,
        modelo_190_detail=request.modelo_190_detail,
        modelo_193_pending_payment=request.modelo_193_pending_payment,
    )
    return LedgerPaymentWithholdingCapture(
        command=command,
        scope=WithholdingWindowScope(modelo=modelo, period=period),
        catalogue_read_revision_id=catalogue_revision_id,
    )


def _exigibility_event(request: LedgerPaymentWithholdingEvidenceRequest) -> WithholdingDatedEvent | None:
    """Return the declared exigibility event, which the request keeps atomic."""
    if request.exigibility_event_id is None or request.exigibility_occurred_on is None:
        return None
    return WithholdingDatedEvent(event_id=request.exigibility_event_id, occurred_on=request.exigibility_occurred_on)


def _perceptor(request: LedgerPaymentWithholdingEvidenceRequest) -> tuple[str, str]:
    """Return the one declared perceptor identity for the request's income kind."""
    if request.modelo_190_detail is not None:
        return request.modelo_190_detail.perceptor_tax_id, request.modelo_190_detail.perceptor_legal_name
    if request.perceptor_nif is None or request.perceptor_name is None:
        raise LedgerPaymentWithholdingEvidenceError("perceptor_identity_missing")
    return request.perceptor_nif, request.perceptor_name


__all__ = [
    "LedgerPaymentWithholdingCapture",
    "LedgerPaymentWithholdingEvidenceError",
    "LedgerPaymentWithholdingEvidenceRequest",
    "build_ledger_payment_withholding_capture",
    "resolve_ledger_payment_transaction",
]
