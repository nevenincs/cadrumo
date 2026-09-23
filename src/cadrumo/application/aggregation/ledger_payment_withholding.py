"""Capture payroll (work-income) withholding anchored to the ledger payment.

The taxpayer as employer is the obligated *retenedor* on the work income it
pays (LIRPF art. 99; RIRPF art. 76), and the withholding is settled through
Modelo 111 with its Modelo 190 annual summary. Work income is recognised when
it is paid or satisfied, so the evidence this producer accepts is the ledger
transaction that paid the employee's net salary: its booked date is the dated
payment event, and the transaction is the source whose identity and revision
the allocation carries.

A bank movement cannot state the payroll terms behind it. The gross
remuneration, the IRPF withheld and the recipient's tax status are legal facts
of the employment relationship, so the caller declares them and this module
checks them against what the ledger proves: an outgoing, euro-denominated
payment whose paid magnitude equals the declared net settlement.

The declared net settlement is bounded above by gross minus withholding rather
than required to equal it. A payroll net is the gross remuneration less the
IRPF withholding *and* the employee's own deductions, such as the Social
Security contribution withheld by the employer (LIRPF art. 19.2.a), union dues
or a court-ordered garnishment. Those deductions do not change the withholding
base, and none of them is visible on the payment, so an equality rule would
refuse every ordinary payslip while a looser rule would invent one.

See Also:
    :mod:`~.withholding_producer`
        The shared producer command this module builds, and the only path that
        mutates withholding evidence.
    :mod:`~.withholding_recognition`
        The recognition derivation whose year and recipient support this
        module defers to rather than restating.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from ...core.aggregation import BindingSourceKind, RetencionScheme
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
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

_WORK_INCOME_MODELO = "111"


class LedgerPaymentWithholdingEvidenceError(CadrumoError):
    """Payload-free refusal while making a ledger payment capture-ready."""

    def __init__(self, refusal_code: str) -> None:
        """Build a refusal that carries only its stable reason token."""
        super().__init__(f"ledger payment withholding evidence refused: {refusal_code}")
        self.refusal_code = refusal_code


class LedgerPaymentWithholdingEvidenceRequest(BaseModel):
    """CLI-safe payroll terms for the one allocation a ledger payment settles.

    The ledger supplies the payment date, currency, paid magnitude and source
    identity. This request holds only what a payment cannot establish: the
    payroll terms, the recipient's tax status, and the Modelo 190 annual
    detail that names the perceptor. It deliberately has no payment-date,
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
    modelo_190_detail: WithholdingObservation

    @field_validator("income_kind")
    @classmethod
    def _only_work_income(cls, value: WithholdingIncomeKind) -> WithholdingIncomeKind:
        """Keep other income kinds on the producers whose evidence proves them."""
        if value is not WithholdingIncomeKind.WORK:
            raise ValueError("ledger payment withholding capture accepts work income only")
        return value


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
) -> LedgerPaymentWithholdingCapture:
    """Derive one work-income producer command from the paying ledger transaction.

    This is the sole ledger-payment-to-withholding translation. Every check
    runs before a command exists, so a refusal can never leave a partial
    capture behind.
    """
    if request.transaction_id != transaction.transaction_id:
        raise LedgerPaymentWithholdingEvidenceError("transaction_identity_mismatch")
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

    payment_on = transaction.raw.booked_date
    evidence = WithholdingRecognitionEvidence(
        applicable_year=applicable_year,
        recipient_tax_status=request.recipient_tax_status,
        recipient_tax_regime=request.recipient_tax_regime,
        income_kind=request.income_kind,
        operation_kind=WithholdingOperationKind.ORDINARY,
        payment_or_satisfaction=WithholdingDatedEvent(event_id=request.payment_event_id, occurred_on=payment_on),
    )
    try:
        recognition = derive_withholding_recognition(evidence, modelo=_WORK_INCOME_MODELO)
    except WithholdingRecognitionError as exc:
        raise LedgerPaymentWithholdingEvidenceError(exc.refusal_code) from exc
    if recognition.recognized_on.year != applicable_year:
        raise LedgerPaymentWithholdingEvidenceError("payment_outside_applicable_year")

    detail = request.modelo_190_detail
    # The bucket-wide catalogue revision changes whenever any other row is
    # written, so it proves only a consistent read. The source revision binds
    # the facts this liability rests on, keeping replay and later corrections
    # addressed to the same payment.
    source_revision_id = content_hash_hex(
        {
            "transaction_id": transaction.transaction_id,
            "currency": transaction.raw.currency,
            "paid_amount": str(transaction.raw.amount),
            "paid_on": payment_on.isoformat(),
            "gross_base": str(request.gross_base),
            "withholding": str(request.withholding_amount),
            "settlement": str(request.net_settlement),
            "perceptor_nif": detail.perceptor_tax_id,
        }
    )
    command = WithholdingEvidenceCaptureCommand(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=transaction.transaction_id,
        source_revision_id=source_revision_id,
        allocation_id=request.allocation_id,
        perceptor_nif=detail.perceptor_tax_id,
        perceptor_name=detail.perceptor_legal_name,
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
        modelo_190_detail=detail,
    )
    recognized_on = recognition.recognized_on
    return LedgerPaymentWithholdingCapture(
        command=command,
        scope=WithholdingWindowScope(
            modelo=_WORK_INCOME_MODELO,
            period=Period.from_year_and_code(recognized_on.year, f"{((recognized_on.month - 1) // 3) + 1}T"),
        ),
        catalogue_read_revision_id=catalogue_revision_id,
    )


__all__ = [
    "LedgerPaymentWithholdingCapture",
    "LedgerPaymentWithholdingEvidenceError",
    "LedgerPaymentWithholdingEvidenceRequest",
    "build_ledger_payment_withholding_capture",
    "resolve_ledger_payment_transaction",
]
