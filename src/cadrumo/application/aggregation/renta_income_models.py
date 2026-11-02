"""Typed rows and refusals of the Renta activity-income ledger projection.

These are the shapes the income aggregation emits: the eligible-row observation,
the traceable exclusion with its reasons, the income an activity narrowing kept
out and the accrued-but-unpaid invoice remainder. The projection mechanics that
produce them live in :mod:`~.renta_income_ledger`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ...core.casilla_id import CasillaId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.prose_elision import IssueDetail
from . import _shared_issue_reasons, renta_income_evidence


class RentaIncomeLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an income observation.

    Every member here EXCLUDES a row. The income pipeline's third outcome —
    a row that is declarable but ungrounded — is deliberately NOT modelled as
    an issue: such a row still contributes, so recording it as an exclusion
    would misstate the aggregation. ``MISSING_TAXABLE_BASE`` is the shared
    vocabulary for the ungrounded condition (spelled identically by the IVA
    and gasto ledgers, where it genuinely does exclude), and the income
    pipeline reports it through the
    :class:`~cadrumo.core.aggregation.LedgerIncomeGrounding` marker on the
    observation instead.
    """

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    UNSUPPORTED_PERIOD = "unsupported_period"
    # Nómina / trabajo entries belong to a separate income category and must
    # not feed an activity-income target.
    TRABAJO_INCOME = "trabajo_income"
    # RIRPF art. 7 cannot place the row: no criterion, no accrual date, or a
    # criterion change that would compute it nowhere. The row enters no box.
    IMPUTATION_UNRESOLVED = "imputation_unresolved"


_DERIVED_WITHHOLDING_MARKERS: frozenset[LedgerWithholdingDerivation] = frozenset(
    {
        LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE,
        LedgerWithholdingDerivation.ALLOCATED_ON_PART_PAYMENT,
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA,
        LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA,
    },
)
"""The markers that assert a real derived figure, so a zero beside one is a defect."""


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class RentaIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating income ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: RentaIncomeLedgerAggregationIssueReason
    detail: IssueDetail


class RentaIncomeObservation(BaseModel):
    """One eligible INCOMING professional-income ledger row.

    Carries the typed gross amount and the target casilla id it feeds. The
    domain registry resolver matches ``target_casilla_id`` against the binding
    selector and sums ``gross_amount`` (or ``taxable_base_amount``) across
    all observations for that casilla depending on the declared fact.

    ``taxable_base_amount`` is the IVA-exclusive base imponible from the
    original invoice (``transaction.taxable_base``).  It feeds the
    ``taxable_base_sum`` fact path used by the rendimiento-neto binding
    (casilla 03).  ``None`` when the transaction carries no explicit
    ``taxable_base``.

    ``grounding`` states which of those two states the row is in, as a fact
    rather than a nullness heuristic every consumer re-derives. A
    ``CASH_FALLBACK`` row declares no invoice substrate, so the only measure
    available is the raw bank-credited amount — net of any retención
    practicada and possibly IVA-inclusive. It is therefore NOT ingresos
    íntegros: the ``ingresos_integros_sum`` fact folds that cash in anyway
    (deliberately — dropping the row would under-declare by its whole value,
    strictly worse) while ``taxable_base_sum`` contributes nothing for it.
    Both are surfaced as a non-blocking advisory rather than being silently
    absorbed; the marker is what the advisory, the evidence bundle, and the
    tests key on.

    ``source_jurisdiction`` propagates the per-transaction ISO 3166-1
    alpha-2 source-jurisdiction provenance from the originating ledger
    row.  LIRPF Art. 8 establishes the universal-base presumption for
    Spanish residents, so the selected income targets aggregate ALL source
    jurisdictions into the same base — the field is preserved for audit and for
    downstream IRNR / Beckham engines that read foreign-source rows.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    gross_amount: Decimal = Field(ge=Decimal("0"))
    taxable_base_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    withheld_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    withheld_derivation: LedgerWithholdingDerivation
    filing_date: date
    source_jurisdiction: str | None = None
    grounding: LedgerIncomeGrounding
    sales_invoice_refusal: renta_income_evidence.SalesInvoiceEvidenceRefusal | None = None

    @model_validator(mode="after")
    def _grounding_matches_declared_base(self) -> Self:
        """Keep the marker and the base it describes from drifting apart.

        The marker is the authority every consumer reads, so a row claiming
        ``SUBSTRATE_DECLARED`` with no base (or ``CASH_FALLBACK`` while
        carrying one) would send the advisory and the aggregation to different
        conclusions about the same row. Refusing the pair here means no
        consumer has to re-check it.
        """
        declared = self.taxable_base_amount is not None
        expected = LedgerIncomeGrounding.SUBSTRATE_DECLARED if declared else LedgerIncomeGrounding.CASH_FALLBACK
        if self.grounding is not expected:
            raise ValueError(
                f"grounding {self.grounding.value!r} contradicts taxable_base_amount="
                f"{self.taxable_base_amount!r}; expected {expected.value!r}",
            )
        return self

    @model_validator(mode="after")
    def _withheld_derivation_matches_the_figure(self) -> Self:
        """Refuse a marker that contradicts the figure beside it.

        The marker exists so a zero can be read: a refused inference and a
        genuine nothing-withheld are both ``Decimal("0")`` and mean opposite
        things. An inference marker sitting on no figure, and a refusal
        carrying the very figure it refused, would destroy that, so both are
        refused here rather than trusted at each consumer.
        """
        if self.withheld_derivation in _DERIVED_WITHHOLDING_MARKERS and self.withheld_amount <= Decimal("0"):
            raise ValueError(
                f"withheld_derivation {self.withheld_derivation.value!r} claims a derived figure "
                f"but withheld_amount is {self.withheld_amount}",
            )
        if (
            self.withheld_derivation is LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE
            and self.withheld_amount != Decimal("0")
        ):
            raise ValueError(
                "a refused withholding inference must not carry the figure it refused; "
                f"withheld_amount is {self.withheld_amount}",
            )
        return self


class UnadmittedActivityIncome(BaseModel):
    """Eligible income an activity narrowing kept out of the target casilla.

    The measurable half of a silence. A casilla fed by an activity-narrowed
    aggregation resolves to zero in two indistinguishable situations: the
    taxpayer genuinely earned nothing that the casilla covers, and the taxpayer
    earned something whose activity nobody ever declared. The computed value is
    the same zero in both, so the difference has to be carried alongside it.

    ``any_activity_declared`` is what separates them, and it is a PREDICATE over
    the excluded rows rather than a copy of any activity code: a row asserting
    some other activity is a positive answer -- the box is correctly empty and
    the operator has spoken -- while a row asserting none leaves the question
    open. Deliberately not a code, both because no code would be the right one to
    name and because the activity type has exactly one stored home.

    ``income_total`` is measured with :func:`_computable_income_amount`, the same
    fact the admitted rows fold through, so the figure an advisory quotes is on
    the same footing as the figure in the box it is quoted against.
    """

    model_config = _STRICT_FROZEN

    target_casilla_id: CasillaId
    """The casilla the narrowing was guarding, named even when nothing was excluded.

    Carried here rather than recovered from the fold, because the fold is EMPTY
    in exactly the situation that matters: a casilla that admitted nothing has no
    key in ``casilla_values``, so a consumer reading the fold alone cannot name
    the box it is reasoning about.
    """
    row_count: int = Field(default=0, ge=0)
    income_total: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    any_activity_declared: bool = False
    """Whether ANY excluded row named an activity, without saying which.

    A predicate rather than the activity type itself, deliberately: the
    single-home gate refuses a class-body annotation naming that type, because
    the accepted design puts the value on a per-activity profile row and has the
    transaction carry a reference. A bool cannot become a second home for the
    fact.

    It is also NARROWER than the enum it stands in for, and this is the site
    that will be wrong first if that ever matters. It can answer "was anything
    declared" and never "was something else declared", so a future advisory
    needing to distinguish a third activity kind here cannot be built on it and
    should not widen it -- by then the profile row is the right source.
    """


class AccruedUnpaidIncome(BaseModel):
    """The part of an issued invoice accruing in the window that no receipt has settled.

    Income under accrual whether or not it is collected, so a part-paid invoice
    counts wholly in its accrual year: its receipts carry their share and this the
    rest. It carries no withholding: the right to deduct one arises only on payment
    (RIRPF art. 78.1; TEAC 00/03187/2011), so what the invoice states on the unpaid
    part is held in ``withholding_unpaid`` and reported.
    """

    model_config = _STRICT_FROZEN

    invoice_id: str
    target_casilla_id: CasillaId
    base: Decimal
    withholding_unpaid: Decimal = Decimal("0")

    @property
    def transaction_id(self) -> str:
        """Name the income row by its invoice; an unpaid invoice has no ledger row."""
        return f"invoice:{self.invoice_id}"

    @property
    def gross_amount(self) -> Decimal:
        """Return the IVA-exclusive base, the income the invoice accrues."""
        return self.base

    @property
    def taxable_base_amount(self) -> Decimal:
        """Return the invoice base."""
        return self.base

    @property
    def withheld_amount(self) -> Decimal:
        """Return zero: nothing is deductible before payment."""
        return Decimal("0")

    @property
    def withheld_derivation(self) -> LedgerWithholdingDerivation:
        """Say nothing enters the credit from this row."""
        return LedgerWithholdingDerivation.NONE_WITHHELD

    @property
    def grounding(self) -> LedgerIncomeGrounding:
        """Say the figure rests on a declared base."""
        return LedgerIncomeGrounding.SUBSTRATE_DECLARED
