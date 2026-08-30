"""Repository-backed Renta actividad-income aggregation.

This is the ledger projection behind the
``ledger_renta_income_aggregation`` source for Modelo 130 and Modelo 100. The
quarterly entry point :func:`aggregate_renta_income_ledger_from_repositories`
loads a :class:`~domain.transactions.TransactionCatalogue` via
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` from the
active bucket and delegates to :func:`aggregate_renta_income_ledger` for
period-scoped aggregation.

Modelo 130 casilla 01 (Ingresos íntegros) accumulates professional-service
revenue from the start of the fiscal year through the end of the declared
quarter. Unlike the expense pipeline, which processes annual periods, the
income pipeline accepts a **quarterly** period token and applies a cumulative
year-to-date window.

Cumulative window rule (RD 439/2007 art. 110.2):
  For period Qn in year Y the window is [Jan 1, Y] through [last day of Qn, Y].
  Q1 covers Jan-Mar; Q2 covers Jan-Jun; Q3 covers Jan-Sep; Q4 covers Jan-Dec.

Only ACTIVE, EUR-denominated, INCOMING transactions whose
``business_classification`` is BUSINESS or MIXED are eligible. Transactions
whose ``value_date`` (or ``booked_date`` if absent) falls outside the
cumulative window are excluded with a traceable issue record.

Modelo 100 uses the annual counterpart
:func:`aggregate_renta_m100_income_ledger`, which keeps the same activity-income
eligibility rules but targets the annual IRPF income leaf. The source-mesh
resolver in :mod:`~._modelo_bindings` chooses the correct path for the
requested modelo and returns the binding values as a
:class:`~._source_mesh.CalculationSourceResolution`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final, NamedTuple, Self

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period, PeriodKind, TipoActividad
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.prose_elision import ElidedProse
from ...core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ...core.identity import TransactionId
from ...core.money import round_to_cents
from ...domain.invoices.decomposition import decompose_invoice
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.components import category_cuota_is_zero_by_law
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.irpf_categories import has_activity_irpf_category, has_employment_irpf_category
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.retencion_parameters import maximum_supported_activity_retencion_rate
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ...domain.transactions.volumen_ingresos import counts_toward_volumen_de_ingresos
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from ._grouping import cumulative_year_to_date_window, fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from ._source_mesh import DIAGNOSTIC_MESSAGE_MAX_LENGTH, CalculationSourceDiagnostic
from .errors import AggregationPeriodError, AggregationValidationError, t

# The only casilla income aggregation feeds for M130 actividad económica direct estimation.
_TARGET_CASILLA_INGRESOS: CasillaId = validated_casilla_id("01", surface="_TARGET_CASILLA_INGRESOS")

_DERIVED_WITHHOLDING_MARKERS: frozenset[LedgerWithholdingDerivation] = frozenset(
    {
        LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE,
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA,
        LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA,
    },
)
"""The markers that assert a real derived figure, so a zero beside one is a defect."""


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
    # Nómina / trabajo entries declare irpf_category="trabajo" — they
    # belong to IRPF rendimientos del trabajo, not actividad económica,
    # and must not feed M130 casillas.
    TRABAJO_INCOME = "trabajo_income"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
_IssueDetail = Annotated[str, ElidedProse(512)]


class SalesInvoiceEvidenceRefusal(StrEnum):
    """Why a linked sales invoice was not trusted for a row's fiscal figures.

    NOT an exclusion. Every member here leaves the row IN the aggregation,
    contributing its bank cash under ``CASH_FALLBACK`` grounding, because the
    taxpayer was paid and that income is declarable whatever state its paperwork
    is in. What the refusal withholds is the invoice's FIGURES, not the row.

    This is the income side of an asymmetry worth stating, because copying the
    expense pipeline's control flow here caused a real regression. An
    unevidenced gasto must NOT be claimed, so that pipeline excludes it. An
    unevidenced ingreso must STILL be declared, so this one degrades it. Same
    checks, opposite consequence; only the checks transfer.

    Spelled per failure rather than as one generic mismatch: which check
    rejected the link is what an operator needs to repair it, and one reason
    would make five different repairs look like one problem.
    """

    BUCKET_MISMATCH = "sales_invoice_bucket_mismatch"
    """The linked invoice belongs to another bucket."""

    UNSUPPORTED_KIND = "unsupported_sales_invoice_kind"
    """The linked invoice is not ISSUED, so it is not this taxpayer's income."""

    LINK_NOT_RECIPROCAL = "sales_invoice_link_mismatch"
    """The invoice does not name this transaction back, so the pairing is unconfirmed."""

    PARTIAL_OR_MULTI_TRANSACTION = "partial_or_multi_transaction_sales_invoice"
    """Several transactions settle this invoice, so no one of them carries its whole base.

    The ordinary instalment case. The rows keep contributing their cash; what
    cannot be done is attribute the invoice's full base to any single one.
    """

    AMOUNT_MISMATCH = "sales_invoice_amount_mismatch"
    """The credit does not match the invoice total net of its declared retención."""

    UNGROUNDED_DECOMPOSITION = "ungrounded_sales_invoice_decomposition"
    """The invoice is correctly linked but its own figures are not interpretable.

    Every other member of this enum asks whether the invoice describes THIS
    transaction. This one asks the separate question of whether the invoice is
    internally coherent at all — whether it declares an IVA treatment, resolves
    its currency, and carries a cuota its category permits. A document can pass
    every linkage guard and still fail that: an invoice with no declared
    :class:`~cadrumo.domain.iva.IvaCategory` reconciles perfectly against its
    payment while remaining ambiguous between untagged and exempt, which is the
    distinction the grounding contract exists to preserve.

    The verdict comes from :func:`~cadrumo.domain.invoices.decompose_invoice`
    rather than from checks re-derived here, so the one authority on invoice
    coherence answers for every consumer.
    """


class RentaIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating income ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: RentaIncomeLedgerAggregationIssueReason
    detail: _IssueDetail


class _SalesInvoiceEvidencePayload(BaseModel):
    """The figures a trusted linked sales invoice contributes to one row.

    Empty when the row links no invoice, which is the ordinary case and not a
    defect. A populated payload has passed every guard in
    :func:`_sales_invoice_evidence_payload`, so its figures may take precedence
    over the transaction's own tax substrate.
    """

    model_config = _STRICT_FROZEN

    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    retencion_amount: Decimal | None = None


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
    Spanish residents, so M130 / M100 aggregate ALL source jurisdictions
    into the same base — the field is preserved for audit and for
    downstream IRNR / Beckham engines that read foreign-source rows.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    gross_amount: Decimal = Field(ge=Decimal("0"))
    taxable_base_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    withheld_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    filing_date: date
    source_jurisdiction: str | None = None
    grounding: LedgerIncomeGrounding
    withheld_derivation: LedgerWithholdingDerivation = LedgerWithholdingDerivation.NOT_APPLICABLE
    sales_invoice_refusal: SalesInvoiceEvidenceRefusal | None = None

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
        things. Two pairings would destroy that and are refused here rather
        than trusted at each consumer -- an inference marker sitting on no
        figure, and a refusal carrying the very figure it refused.

        The remaining members are deliberately permissive about the amount.
        :attr:`LedgerWithholdingDerivation.NOT_APPLICABLE` is the field
        default, so it is also what an observation built without reference to
        this axis carries; refusing a figure beside it would make the default
        unusable rather than make anything safer. The guarantee that matters
        lives on the production path, where
        :func:`_build_income_observation` always states a marker it derived
        together with the amount -- pinned by
        ``test_the_builder_never_emits_an_unmarked_withholding``.
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


class RentaIncomeLedgerAggregation(
    LedgerAggregationResultBase[RentaIncomeObservation, RentaIncomeLedgerAggregationIssue],
):
    """Cumulative income observations for one M130 quarter window.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.

    ``unadmitted_activity_income`` is populated only by a projection that
    NARROWS rows by activity -- today the Modelo 131 agrarian volumen. ``None``
    on the Modelo 130 and Modelo 100 paths states that no narrowing ran, which is
    not the same claim as a narrowing that excluded nothing, and the two must
    stay distinguishable: the second is a fact about this taxpayer's ledger, the
    first is a fact about which projection was asked for.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    unadmitted_activity_income: UnadmittedActivityIncome | None = None


def _load_income_invoices(
    *,
    bucket_id: str,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None,
) -> InvoiceCatalogue:
    """Load the bucket's invoice catalogue for sales-invoice evidence.

    Both income entry points call this, and both must: the single production
    call site chooses between the quarterly and annual aggregators, so threading
    one and not the other would leave the two halves grounding differently --
    the asymmetry this evidence path exists to remove.
    """
    repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.invoice_bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    return repository.load()


def aggregate_renta_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the transaction catalogue and aggregate cumulative M130 income.

    Returns a :class:`RentaIncomeLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    invoices = _load_income_invoices(bucket_id=bucket_id, invoice_repository=invoice_repository)
    # Only the cumulative in-window subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``.
    window = cumulative_year_to_date_window(period)
    partition = repository.partition_by_date_range(window.start, window.end)
    result = aggregate_renta_income_ledger(partition.in_window, invoices, bucket_id=bucket_id, period=period)
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
) -> RentaIncomeLedgerAggregation:
    """Aggregate INCOMING professional-income transactions into M130 casilla 01.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        invoices: The bucket's :class:`~domain.invoices.InvoiceCatalogue`, whose
            linked sales invoices supply the base, cuota and retención for rows
            that reference one. Optional so an in-process caller holding no
            invoices need not construct an empty catalogue; the production entry
            point above always loads and passes the real one, so the evidence
            path is wired rather than latent.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.

    Returns a :class:`RentaIncomeLedgerAggregation` covering the
    cumulative fiscal window. ``period`` must be quarterly. The cumulative
    window extends from Jan 1 of the
    period's year through the last day of the declared quarter,
    implementing the year-to-date accumulation rule for IRPF pagos
    fraccionados (RD 439/2007 art. 110.2).
    """
    window = cumulative_year_to_date_window(period)
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()

    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []

    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_income_transaction(
            transaction,
            invoices=resolved_invoices,
            bucket_id=bucket_id,
            cumulative_start=window.start,
            cumulative_end=window.end,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _income_casilla_aggregation(window.period, observations)
    return RentaIncomeLedgerAggregation(
        modelo=Modelo.M130.value,
        period=window.period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


# Modelo 100 estimación-directa "Ingresos de explotación" leaf. The annual IRPF
# return aggregates the same actividad-económica income the M130 quarterly path
# sums, but over the full ejercicio and into the M100 income leaf rather than the
# M130 cumulative casilla.
_TARGET_CASILLA_M100_INGRESOS: CasillaId = validated_casilla_id(
    "0171",
    surface="_TARGET_CASILLA_M100_INGRESOS",
)


def aggregate_renta_m100_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the catalogue and aggregate the annual Modelo 100 actividad income.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for the requested annual period.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    invoices = _load_income_invoices(bucket_id=bucket_id, invoice_repository=invoice_repository)
    # Only the in-window ejercicio subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``. Non-annual periods fall back to
    # the unfiltered load so the aggregation's own period validation still
    # raises the same error.
    if period.kind is not PeriodKind.ANNUAL:
        return aggregate_renta_m100_income_ledger(repository.load(), invoices, bucket_id=bucket_id, period=period)
    partition = repository.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_renta_m100_income_ledger(partition.in_window, invoices, bucket_id=bucket_id, period=period)
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_m100_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
) -> RentaIncomeLedgerAggregation:
    """Aggregate annual actividad-económica income from a :class:`TransactionCatalogue` into Modelo 100 casilla 0171.

    The annual counterpart of :func:`aggregate_renta_income_ledger`: it applies the
    same actividad-económica eligibility (excluding nómina/trabajo and personal
    flows) over the FULL ejercicio (Jan 1 to Dec 31 of ``period.filing_year``) and targets
    the M100 "Ingresos de explotación" leaf (0171) instead of the M130 cumulative
    casilla. ``period`` must be the annual period. The :class:`InvoiceCatalogue`
    passed as ``invoices`` is consulted when classifying each transaction; an
    empty catalogue is used when it is omitted.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` built from eligible transactions.
    """
    if period.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    window_start = date(period.filing_year, 1, 1)
    window_end = date(period.filing_year, 12, 31)
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()

    # The classifier targets the M130 casilla 01; every eligible observation is
    # re-targeted to the M100 income leaf 0171.
    projected = _project_income_onto_casilla(
        transactions,
        invoices=resolved_invoices,
        bucket_id=bucket_id,
        window_start=window_start,
        window_end=window_end,
        target_casilla_id=_TARGET_CASILLA_M100_INGRESOS,
    )
    observations = list(projected.observations)
    issues = list(projected.issues)

    casilla_aggregation = _m100_income_casilla_aggregation(period, observations)
    return RentaIncomeLedgerAggregation(
        modelo=Modelo.M100.value,
        period=period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _m100_income_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaIncomeObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=Modelo.M100.value,
        period=period,
        amount_fn=_computable_income_amount,
    )


_TARGET_CASILLA_M131_AGRARIO: CasillaId = validated_casilla_id(
    "05",
    surface="_TARGET_CASILLA_M131_AGRARIO",
)

_M131_AGRARIO_ACTIVITY_SELECTOR: Final[str] = (
    "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva"
)


def _m131_agrarian_activity_codes() -> frozenset[TipoActividad]:
    """Return the Modelo 036 codes whose income feeds Modelo 131 casilla 05.

    Delegates to the one reader for ``m036-tipo-actividad-code-set`` parameters
    rather than splitting the string here. Several unrelated selectors share that
    unit -- the four art. 95 partitions and this art. 110.1.c) set -- and a second
    parser is a second place the unit check and the unknown-token refusal drift.

    The set is NOT the art. 95 agrícola/ganadera one: that carries no forestal code,
    so borrowing it would drop a forestal filer's entire quarterly volume.

    Raises:
        TransactionValidationError: If the selector parameter is absent or malformed.
    """
    return tipo_actividad_code_set(_M131_AGRARIO_ACTIVITY_SELECTOR)


def aggregate_renta_m131_agrario_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> RentaIncomeLedgerAggregation:
    """Load the catalogue and aggregate the Modelo 131 agrarian quarterly volume.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for the requested quarter.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    invoices = _load_income_invoices(bucket_id=bucket_id, invoice_repository=invoice_repository)
    return aggregate_renta_m131_agrario_income_ledger(
        repository.load(),
        invoices,
        bucket_id=bucket_id,
        period=period,
    )


def aggregate_renta_m131_agrario_income_ledger(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None = None,
    *,
    bucket_id: str,
    period: Period,
) -> RentaIncomeLedgerAggregation:
    """Aggregate the agrarian volumen de ingresos into Modelo 131 casilla 05.

    Two filters separate this from the Modelo 130 path, and both are legal rather
    than incidental:

    * **Activity.** Only rows whose declared :class:`~core.TipoActividad` is in the
      registry's art. 110.1.c) selector contribute. A row with no declared activity
      contributes NOTHING here — the opposite of the concept default below, and
      deliberately so. Silence about activity cannot mean "agrarian": routing an
      undeclared row into casilla 05 would put a non-agrarian filer's income into an
      agrarian box, and the same row is already claimed by the estimación-objetiva
      side of the form. Under-filling a box the operator can still complete by hand
      is recoverable; mis-routing income between two boxes of one return is not.
    * **Concept.** Rows whose :class:`~core.ConceptoIngreso` art. 110.1.c) excludes —
      subvenciones de capital and indemnizaciones — are dropped. An undeclared
      concept IS included, because an unmarked receipt is far more likely to be
      ordinary income than an exceptional one.

    The window is the quarter itself rather than the cumulative year-to-date the
    Modelo 130 path uses: art. 110.1.c) fixes the payment on *el volumen de ingresos
    del trimestre*, and the AEAT Modelo 131 instrucciones for casilla 05 repeat it —
    *el volumen de ingresos del trimestre por el que se realiza el pago fraccionado*.
    Modelo 131 carries no cross-quarter cumulative on this leg.

    Args:
        transactions: The :class:`TransactionCatalogue` to project.
        invoices: The :class:`InvoiceCatalogue` consulted when classifying; an
            empty catalogue when omitted.
        bucket_id: The active profile bucket.
        period: The quarter being filed.

    Returns:
        The :class:`RentaIncomeLedgerAggregation` for casilla 05.

    Raises:
        AggregationPeriodError: If ``period`` is not a quarter.
    """
    if period.kind is not PeriodKind.QUARTERLY:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    resolved_invoices = invoices if invoices is not None else InvoiceCatalogue()
    agrarian_codes = _m131_agrarian_activity_codes()

    projected = _project_income_onto_casilla(
        transactions,
        invoices=resolved_invoices,
        bucket_id=bucket_id,
        window_start=period.start_date,
        window_end=period.end_date,
        target_casilla_id=_TARGET_CASILLA_M131_AGRARIO,
        admits=lambda transaction: (
            transaction.tipo_actividad in agrarian_codes
            and counts_toward_volumen_de_ingresos(transaction.concepto_ingreso)
        ),
    )

    return RentaIncomeLedgerAggregation(
        modelo=Modelo.M131.value,
        period=period,
        observations=projected.observations,
        issues=projected.issues,
        casilla_aggregation=fold_casilla_observations(
            projected.observations,
            modelo=Modelo.M131.value,
            period=period,
            amount_fn=_computable_income_amount,
        ),
        unadmitted_activity_income=_unadmitted_activity_income(
            transactions,
            projected.unadmitted,
            target_casilla_id=_TARGET_CASILLA_M131_AGRARIO,
        ),
    )


def _unadmitted_activity_income(
    transactions: TransactionCatalogue,
    unadmitted: Sequence[RentaIncomeObservation],
    *,
    target_casilla_id: CasillaId,
) -> UnadmittedActivityIncome:
    """Measure the income the art. 110.1.c) activity narrowing kept out.

    Always returns a value, including the all-zero one. An empty census is a
    positive statement -- the narrowing ran and excluded nothing -- and a
    consumer that had to read ``None`` for it could not tell that apart from a
    projection where no narrowing ran at all.

    The declared-activity predicate reads each excluded row back off the
    catalogue rather than off the observation, because the observation carries no
    activity and must not start to: the activity type has one stored home, and a
    second copy on an aggregation row would be the drift that placement exists to
    avoid. Reading it here is a function-local question about a row already in
    hand, not a new home for the fact.
    """
    if not unadmitted:
        return UnadmittedActivityIncome(target_casilla_id=target_casilla_id)
    by_id = {transaction.transaction_id: transaction for transaction in transactions.values()}
    return UnadmittedActivityIncome(
        target_casilla_id=target_casilla_id,
        row_count=len(unadmitted),
        income_total=sum(
            (_computable_income_amount(observation) for observation in unadmitted),
            start=Decimal("0"),
        ),
        # Indexed rather than searched, and unguarded on purpose: every
        # unadmitted observation was built from a row of this catalogue, so a
        # missing key is a broken invariant worth raising rather than a state to
        # absorb into a quiet ``False``.
        any_activity_declared=any(
            by_id[observation.transaction_id].tipo_actividad is not None for observation in unadmitted
        ),
    )


class _ProjectedIncome(NamedTuple):
    """Observations and issues from one pass over a catalogue.

    ``unadmitted`` carries the observations an ``admits`` narrowing kept OUT.
    They are eligible income by every other rule the pipeline applies -- same
    classifier, same window -- and were excluded solely by the row filter, which
    is what makes them the honest denominator for "this period carries income the
    target casilla did not admit". Empty whenever ``admits`` is ``None``, so the
    Modelo 100 and Modelo 130 paths carry nothing extra.
    """

    observations: tuple[RentaIncomeObservation, ...]
    issues: tuple[RentaIncomeLedgerAggregationIssue, ...]
    unadmitted: tuple[RentaIncomeObservation, ...] = ()


def _project_income_onto_casilla(
    transactions: TransactionCatalogue,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    window_start: date,
    window_end: date,
    target_casilla_id: CasillaId,
    admits: Callable[[Transaction], bool] | None = None,
) -> _ProjectedIncome:
    """Classify a catalogue once and re-target every eligible observation.

    The Modelo 100 and Modelo 131 aggregations differ from the Modelo 130 one in
    three ways and no more: the window, the casilla, and whether rows are narrowed
    before classification. Everything else -- the lifecycle skip, the classifier
    call, the issue/observation split -- was written out identically in each, so a
    change to the eligibility contract had to be made in every copy or silently
    hold in only some.

    Args:
        transactions: The catalogue to project.
        invoices: Consulted when classifying each transaction.
        bucket_id: The active profile bucket.
        window_start: First day the classifier treats as in-window.
        window_end: Last day the classifier treats as in-window.
        target_casilla_id: The casilla every eligible observation is re-targeted to.
        admits: Optional row filter deciding which rows reach the casilla.
            ``None`` admits every active row, which is what the M100 and M130
            paths want. A rejected row is still CLASSIFIED, so its income can be
            counted, but it contributes to ``unadmitted`` rather than to
            ``observations``.

    Returns:
        The projected observations, the issues raised along the way, and the
        eligible income the ``admits`` narrowing kept out.
    """
    observations: list[RentaIncomeObservation] = []
    issues: list[RentaIncomeLedgerAggregationIssue] = []
    unadmitted: list[RentaIncomeObservation] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        admitted = admits is None or admits(transaction)
        outcome = _classify_income_transaction(
            transaction,
            invoices=invoices,
            bucket_id=bucket_id,
            cumulative_start=window_start,
            cumulative_end=window_end,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaIncomeLedgerAggregationIssue):
            # A rejected row's issues are DISCARDED rather than reported. An
            # issue is a traceable exclusion from the casilla this pass feeds,
            # and a row the narrowing already excluded was never a candidate for
            # it -- reporting why it also failed a currency or window gate would
            # describe an exclusion that did not happen. The narrowing's own
            # consequence is reported once, in aggregate, off ``unadmitted``.
            if admitted:
                issues.append(outcome)
            continue
        retargeted = outcome.model_copy(update={"target_casilla_id": target_casilla_id})
        (observations if admitted else unadmitted).append(retargeted)
    return _ProjectedIncome(tuple(observations), tuple(issues), tuple(unadmitted))


def _classify_income_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    cumulative_start: date,
    cumulative_end: date,
) -> RentaIncomeObservation | RentaIncomeLedgerAggregationIssue | None:
    """Filter one ledger transaction against the M130 income pipeline.

    Returns a :class:`RentaIncomeObservation` for an eligible receipt, a
    :class:`RentaIncomeLedgerAggregationIssue` for an INCOMING row that fails a
    gate, or ``None`` for an OUTGOING row this income pipeline does not own —
    deductible OUTGOING expenses are aggregated into casilla 02 by the
    companion ``ledger_renta_gastos_pago_fraccionado_aggregation`` pipeline
    (:mod:`~._renta_gasto_ledger`), so the income pass skips them silently
    rather than emitting a misleading "expense dropped" advisory.
    """
    transaction_id = transaction.transaction_id

    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        # Operator reviewed and deliberately excluded this row from filing (a
        # final disposition): omit it silently. This short-circuits before the
        # ``irpf_category=actividad_economica`` business override in
        # ``_income_business_proportion`` so an excluded row can never slip back into
        # aggregation through the category tag.
        return None
    if transaction.direction is not TransactionDirection.INCOMING:
        # OUTGOING (and any non-income) rows are out of scope for the income
        # pass. Deductible business expenses are owned by the gasto pipeline;
        # they are no longer surfaced here as a drop (no-silent-under-declaration
        # is upheld by that pipeline aggregating them into casilla 02).
        return None
    if is_non_eur_without_conversion(transaction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta income",
        )

    # Nómina entries (irpf_category="trabajo") belong to rendimientos del
    # trabajo and must not feed M130 actividad-económica casillas.
    if has_employment_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME,
            detail=(
                f"irpf_category {transaction.irpf_category!r} belongs to rendimientos del trabajo, "
                "not actividad económica; excluded from M130"
            ),
        )

    proportion = _income_business_proportion(transaction)
    if proportion is None:
        reason = (
            RentaIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else RentaIncomeLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=reason,
            detail=(f"business classification {transaction.business_classification.value!r} cannot feed Renta income"),
        )
    # Use the EUR projection after rejecting unconverted non-EUR rows above, so a
    # converted foreign-currency receipt contributes its EUR equivalent while a
    # domestic row retains its raw amount (mirrors the expense pipeline's
    # ``effective_eur_amount`` usage in ``_renta_ledger.py``).
    gross_amount = effective_eur_amount(transaction) * proportion

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if not (cumulative_start <= filing_date <= cumulative_end):
        return RentaIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the cumulative income window",
        )

    # taxable_base carries the IVA-exclusive base imponible when set; it
    # feeds the taxable_base_sum fact path for the rendimiento-neto binding.
    evidence, evidence_refusal = _sales_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction=transaction,
    )

    # The linked invoice's own base takes precedence over the transaction's tax
    # substrate, with the transaction field as fallback -- the same ordering the
    # expense pipeline uses. A grounded row therefore also stops reporting
    # CASH_FALLBACK below, correctly: the substrate now genuinely exists.
    # The transaction fallback goes through the EUR-equivalent accessor:
    # ``transaction.taxable_base`` is denominated in the row's native
    # currency (see ``domain.transactions.tests.test_gross_invariant``), so a
    # converted foreign-currency row needs the same fx_rate projection the
    # gross amount above already received.
    declared_base = (
        evidence.taxable_base if evidence.taxable_base is not None else effective_eur_taxable_base(transaction)
    )
    # Scaled by the SAME proportion the gross above carries, never a second
    # decision: the two figures describe one receipt, so a rule that divided one
    # and not the other would declare a fraction of the income while the
    # retención derived from the undivided base stayed whole.
    taxable_base_amount: Decimal | None = None if declared_base is None else declared_base * proportion

    withheld = _income_withheld_amount(transaction, evidence=evidence)

    return RentaIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=_TARGET_CASILLA_INGRESOS,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        withheld_amount=withheld.amount,
        withheld_derivation=withheld.derivation,
        sales_invoice_refusal=evidence_refusal,
        filing_date=filing_date,
        source_jurisdiction=transaction.source_jurisdiction,
        grounding=(
            LedgerIncomeGrounding.SUBSTRATE_DECLARED
            if taxable_base_amount is not None
            else LedgerIncomeGrounding.CASH_FALLBACK
        ),
    )


def _sales_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction: Transaction,
) -> tuple[_SalesInvoiceEvidencePayload, SalesInvoiceEvidenceRefusal | None]:
    """Return the figures a linked sales invoice contributes, or why it is refused.

    Derive-on-read, mirroring the expense pipeline's
    ``_purchase_invoice_evidence_payload``: nothing is copied onto the
    transaction at link time, so a corrected invoice is reflected on the next
    aggregation and no stale figure can outlive it.

    One guard differs from the expense side, and the difference is the point. An
    expense pays the whole contraprestación, so that side asserts the cash
    equals ``grand_total``. A sales invoice subject to retención is paid NET --
    the payer withholds and remits the retención on the taxpayer's account -- so
    the bank credit is ``grand_total - retention_amount``. Asserting equality
    against ``grand_total`` here would refuse precisely the net-paid
    professional invoices this evidence path exists to ground; asserting it
    against the cash without the retención term would accept an invoice that
    does not describe the payment.
    """
    invoice_id = transaction.invoice_id
    if invoice_id is None:
        return _SalesInvoiceEvidencePayload(), None
    invoice = invoices.get(invoice_id)
    if invoice is None:
        # Not an error: an unresolvable link is already reported by the ledger
        # surface, and the income pipeline's job here is only to decide whether
        # trustworthy invoice figures exist. Falling through leaves the row on
        # its own substrate and its existing grounding marker.
        return _SalesInvoiceEvidencePayload(), None
    transaction_id = transaction.transaction_id
    if invoice.bucket_id != bucket_id:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.BUCKET_MISMATCH
    if invoice.kind is not InvoiceKind.ISSUED:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.UNSUPPORTED_KIND
    if transaction_id not in invoice.linked_transaction_ids:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.LINK_NOT_RECIPROCAL
    if len(invoice.linked_transaction_ids) != 1:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.PARTIAL_OR_MULTI_TRANSACTION
    expected_cash = invoice.grand_total - (invoice.retention_amount or Decimal("0"))
    if abs(transaction.raw.amount) != expected_cash:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH
    # Linkage is established by this point; coherence is a separate question and
    # the guards above cannot answer it. Delegated rather than re-derived: the
    # decomposition contract is the single authority on whether an invoice's own
    # figures are legally interpretable, and consulting it here is what makes a
    # correctly-linked but untagged invoice visible instead of silently grounded.
    if not decompose_invoice(invoice).is_grounded:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION
    return (
        _SalesInvoiceEvidencePayload(
            taxable_base=invoice.base_total,
            iva_amount=invoice.iva_total,
            retencion_amount=invoice.retention_amount,
        ),
        None,
    )


def unusable_sales_invoice_diagnostics(
    observations: Sequence[RentaIncomeObservation],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Surface rows whose linked sales invoice could not be trusted.

    These rows are NOT excluded -- they contribute their bank cash, because the
    taxpayer was paid and that income is declarable whatever state its paperwork
    is in. What they lost is the invoice's base, cuota and retención, so the
    figure they contribute is the credited cash rather than the ingresos
    íntegros the casilla asks for. Without this advisory that downgrade is
    invisible: the row looks exactly like one that never had an invoice at all.

    One advisory per refusal reason, not per row: the actionable unit is "these
    links are unusable, and this is what is wrong with them", and a per-row
    advisory trains operators to ignore the channel. The id sample is fitted to
    the message budget by :func:`fitted_diagnostic_id_list`, so a long list
    degrades to a count instead of raising out of the diagnostic and taking the
    calculation down with it.
    """
    by_reason: dict[SalesInvoiceEvidenceRefusal, list[RentaIncomeObservation]] = {}
    for observation in observations:
        if observation.sales_invoice_refusal is not None:
            by_reason.setdefault(observation.sales_invoice_refusal, []).append(observation)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for reason in sorted(by_reason, key=lambda member: member.value):
        rows = by_reason[reason]
        total = sum((row.gross_amount for row in rows), Decimal("0"))
        preamble = (
            f"{len(rows)} income row(s) totalling {total} EUR link a sales invoice that could not be "
            f"trusted ({reason.value}), so they declare bank cash instead of the invoice base and their "
            f"retención credit is lost. Repair the link or record the base directly. Transactions: "
        )
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unusable_sales_invoice_evidence",
                source_kind="ledger_renta_income_aggregation",
                resolver_id=resolver_id,
                message=preamble
                + fitted_diagnostic_id_list(
                    sorted(row.transaction_id for row in rows),
                    budget=DIAGNOSTIC_MESSAGE_MAX_LENGTH - len(preamble),
                ),
            ),
        )
    return tuple(diagnostics)


def fitted_diagnostic_id_list(identifiers: Sequence[str], *, budget: int) -> str:
    """Render ``identifiers`` into at most ``budget`` characters, stating omissions.

    Shows as many ids as fit alongside the "(and N more)" suffix that describes
    the ones it dropped -- the suffix is part of the budget, because a
    truncation notice that itself overflows would defeat the cap it exists to
    respect.

    Degrades rather than raises: when even one id plus its suffix cannot fit, it
    reports the bare count. The caller is an advisory about a measurement risk,
    so losing the id sample is acceptable where losing the whole diagnostic --
    and with it the calculation -- is not.
    """
    total = len(identifiers)
    for shown in range(total, 0, -1):
        remainder = total - shown
        candidate = ", ".join(identifiers[:shown]) + (f" (and {remainder} more)" if remainder else "")
        if len(candidate) <= budget:
            return candidate
    fallback = f"{total} transaction(s), ids omitted to fit the diagnostic length limit"
    return fallback if len(fallback) <= budget else ""


def _income_business_proportion(transaction: Transaction) -> Decimal | None:
    """Return the share of one income row that is activity income, or ``None``.

    The single proportion decision for the row: every money figure the
    observation carries is scaled by this one value, so the gross and the
    taxable base cannot disagree about how much of the receipt is the
    activity's.

    When ``irpf_category`` is explicitly set to ``"actividad_economica"`` the
    transaction is already classified as a professional-activity receipt and
    ``business_classification`` is treated as ``BUSINESS`` by definition (the
    category tag is the authoritative signal). This avoids the common case
    where a transaction is tagged with ``irpf_category=actividad_economica``
    before the broader ``business_classification`` sweep has run.

    That short-circuit is also the legally correct answer to a MIXED
    classification on an activity receipt, not merely a convenience. Partial
    affectation is a property of ASSETS: LIRPF art. 29.2 (Ley 35/2006,
    BOE-A-2006-20764) limits it to "elementos patrimoniales que sirvan sólo
    parcialmente al objeto de la actividad económica", and it reaches the
    rendimiento neto through the deductibility of the gastos those assets
    generate (art. 28.1). Nothing in art. 27-30 divides an INGRESO by a usage
    percentage -- a client's payment for professional services is wholly an
    ingreso íntegro of the activity however the taxpayer's own desk, car or
    flat happens to be split. The retención the payer withholds on it agrees:
    RIRPF art. 95.1 (RD 439/2007) fixes the rate "sobre los ingresos íntegros
    satisfechos", a fact about the payment, carrying no affectation term at
    all. So an activity-tagged row is undivided on every figure, and because
    ``_income_withheld_amount`` derives a retención for activity rows only,
    every row that carries one is a row this returns ``1`` for.
    """
    if has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        # The explicit IRPF category is the authoritative M130 eligibility gate.
        return Decimal("1")
    return business_proportion(transaction.business_classification, transaction.business_pct)


def _computable_income_amount(observation: RentaIncomeObservation) -> Decimal:
    """Return the fiscally computable ingreso for one observation.

    Mirrors the registry's ``ingresos_integros_sum`` fact: the
    IVA-exclusive ``taxable_base_amount`` when the transaction carries an
    explicit IVA tagging, falling back to ``gross_amount`` when no base is
    declared. IVA repercutido is collected on behalf of Hacienda and is
    not computable income, so the two surfaces (this projection and the
    binding resolver) must agree per the one-aggregation-path discipline.
    """
    if observation.taxable_base_amount is not None:
        return observation.taxable_base_amount
    return observation.gross_amount


class _WithheldInference(NamedTuple):
    """One row's derived retención and the route that produced it."""

    amount: Decimal
    derivation: LedgerWithholdingDerivation


def _determinable_cuota(transaction: Transaction) -> Decimal | None:
    """Return the row's IVA cuota when it can be known, else ``None``.

    A recorded ``iva_amount`` is the cuota. Failing that, the declared IVA
    category can still determine it: for a category whose cuota is zero by law
    the absent field is not missing data, it is the operation having no cuota
    to record. Reading the Axis-A table rather than testing for nullness is
    what separates those two -- ``iva_amount is None`` alone cannot say whether
    an exempt supply was declared or nothing was tagged at all.

    The table is keyed on the category AND the invoice kind, because the same
    category resolves differently on each side: a domestic reverse-charge
    operation carries no cuota when issued and a self-assessed one when
    received. These are actividad-económica RECEIPTS, so the taxpayer is always
    the issuer -- an income row is the issued side by construction, which is
    why the kind is fixed here rather than read off the row.

    Returns ``None`` only when the cuota is genuinely unknown.
    """
    if transaction.iva_amount is not None:
        return transaction.iva_amount
    category = transaction.iva_category
    if category is not None and category_cuota_is_zero_by_law(category, InvoiceKind.ISSUED):
        return Decimal("0")
    return None


def _income_withheld_amount(
    transaction: Transaction,
    *,
    evidence: _SalesInvoiceEvidencePayload | None = None,
) -> _WithheldInference:
    """Derive the retención practicada on one income row.

    Bounded inference only: the figure is the declared invoice gross minus the
    cash actually received. The base is never reconstructed from the cash by
    assuming a rate -- selecting the applicable rate (15 %, 7 %, a sectoral or
    convenio figure) is a per-row legal fact this application cannot determine,
    and inventing it would manufacture legal behaviour rather than read it.

    The result is capped by the registry maximum supported rate. That bound
    also exists on the :class:`~cadrumo.domain.transactions.Transaction` gross
    invariant, which refuses construction outright -- but only for rows
    carrying BOTH a base and a cuota, since it returns early when either is
    absent. The zero-cuota rows admitted here never meet it, so for them this
    is the only bound, and applying it uniformly keeps one rule rather than two
    that must be read together to know whether a row was checked.
    """
    if not has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NOT_APPLICABLE)
    # Declared-first, by design. A retención the linked invoice states is the
    # figure the document carries; the inference below reconstructs one from
    # what reached the bank. The declared figure is preferred and needs no
    # bound because nothing was inferred.
    if evidence is not None and evidence.retencion_amount is not None and evidence.retencion_amount > Decimal("0"):
        return _WithheldInference(
            evidence.retencion_amount,
            LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE,
        )
    if transaction.taxable_base is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    cuota = _determinable_cuota(transaction)
    if cuota is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    derivation = (
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA
        if transaction.iva_amount is not None
        else LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    )
    invoice_gross = transaction.taxable_base + cuota
    cash_received = abs(transaction.raw.amount)
    if invoice_gross <= cash_received:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NONE_WITHHELD)
    inferred = invoice_gross - cash_received
    maximum_supported = round_to_cents(transaction.taxable_base * maximum_supported_activity_retencion_rate())
    if round_to_cents(inferred) > maximum_supported:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE)
    return _WithheldInference(inferred, derivation)


def _income_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaIncomeObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=Modelo.M130.value,
        period=period,
        amount_fn=_computable_income_amount,
    )


__all__ = [
    "RentaIncomeLedgerAggregation",
    "RentaIncomeLedgerAggregationIssue",
    "RentaIncomeLedgerAggregationIssueReason",
    "RentaIncomeObservation",
    "SalesInvoiceEvidenceRefusal",
    "UnadmittedActivityIncome",
    "aggregate_renta_income_ledger",
    "aggregate_renta_income_ledger_from_repositories",
    "aggregate_renta_m100_income_ledger",
    "aggregate_renta_m100_income_ledger_from_repositories",
]
