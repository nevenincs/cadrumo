"""Repository-backed Modelo 151 impatriado Spanish-source income aggregation.

This is the ledger projection behind the
``ledger_impatriado_income_aggregation`` source for Modelo 151 (régimen
especial de trabajadores desplazados, "Ley Beckham", art. 93 LIRPF). The annual
entry point :func:`aggregate_impatriado_income_ledger_from_repositories` loads a
:class:`~domain.transactions.TransactionCatalogue` from the active bucket
through :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` and
delegates to :func:`aggregate_impatriado_income_ledger`.

Unlike the Modelo 130 / Modelo 100 actividad-económica income pipeline
(:mod:`~._renta_income_ledger`), which admits worldwide income into the
resident-IRPF base (LIRPF art. 8), the impatriado base is legally
source-scoped: art. 93.2 taxes the impatriado by the IRNR scope rules, so its
``impatriado.base-liquidable-general`` casilla admits ONLY Spanish-source
income. The declared per-row ``source_jurisdiction`` axis — which the CLI
create-boundary gate compels an impatriado profile to supply on every ledger
row — is finally consumed here:

- an INCOMING row whose ``source_jurisdiction`` resolves to ``ES`` folds into
  the impatriado base;
- a foreign-source row (``source_jurisdiction`` set to any non-``ES`` code) is
  segregated out of the base and surfaced as a typed
  :attr:`ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED`
  issue carrying the rejected jurisdiction code (art. 93.2 / art. 25.1.f
  TRLIRNR segregation);
- a jurisdiction-unresolved row (``source_jurisdiction is None``) is NEVER
  silently coerced to ``ES``: it fails loud as the same segregation issue with
  an unresolved-jurisdiction detail (``no-silent-under-declaration``).

The impatriado base admits ``trabajo`` income — the exact income class the M130
pipeline routes OUT — because the Beckham base is predominantly rendimientos
del trabajo (nómina). The two pipelines are complementary, not shared.

The savings escala (art. 93.2.e.2º → art. 25.1.f TRLIRNR: the parte del ahorro)
is out of scope here and blocked on a separate corpus ingest; the base casilla
is labelled "excluida la parte del ahorro" to keep that deferral honest.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period, PeriodKind
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.prose_elision import ElidedProse
from ...core.country_code import CountryCodeAlpha2
from ...core.identity import TransactionId
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.irpf_categories import has_activity_irpf_category, has_employment_irpf_category
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import effective_eur_amount, effective_eur_taxable_base, is_non_eur_without_conversion
from ._grouping import fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from .errors import AggregationPeriodError, AggregationValidationError, t

# The Modelo 151 base liquidable general (régimen impatriados, excluida la parte
# del ahorro). The impatriado income aggregation folds Spanish-source income into
# this single base casilla; the flat 24/47 escala (art. 93.2.e.1º) then computes
# the cuota íntegra from it.
_TARGET_CASILLA_IMPATRIADO_BASE: CasillaId = validated_casilla_id(
    "impatriado.base-liquidable-general",
    surface="_TARGET_CASILLA_IMPATRIADO_BASE",
)

# ISO 3166-1 alpha-2 code for Spain. The impatriado base admits only rows whose
# declared source jurisdiction equals this code (art. 93.2 IRNR scope).
_SPANISH_SOURCE_JURISDICTION: str = "ES"


class ImpatriadoIncomeLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not fold into the impatriado base."""

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    UNSUPPORTED_PERIOD = "unsupported_period"
    # art. 93.2 LIRPF / art. 25.1.f TRLIRNR: the impatriado is taxed by IRNR
    # scope rules, so foreign-source income is segregated OUT of the base
    # liquidable general. This reason fires for a row whose declared
    # source_jurisdiction is a non-ES code (foreign-source) OR is unresolved
    # (None) — an unresolved jurisdiction is NEVER silently coerced to ES.
    BECKHAM_FOREIGN_SOURCE_SEGREGATED = "beckham_foreign_source_segregated"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
_IssueDetail = Annotated[str, ElidedProse(512)]


class ImpatriadoIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating impatriado income ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: ImpatriadoIncomeLedgerAggregationIssueReason
    detail: _IssueDetail
    # The rejected ISO 3166-1 alpha-2 source-jurisdiction code for a
    # BECKHAM_FOREIGN_SOURCE_SEGREGATED row; ``None`` when the row carried no
    # declared jurisdiction (the unresolved case), so an auditor can tell a
    # foreign-source segregation apart from an unresolved-provenance one.
    rejected_source_jurisdiction: str | None = None


class ImpatriadoIncomeObservation(BaseModel):
    """One eligible INCOMING Spanish-source income ledger row for the impatriado base.

    Carries the typed gross amount and the target casilla id it feeds
    (``impatriado.base-liquidable-general``). The domain registry resolver sums
    the fiscally computable ingreso (``taxable_base_amount`` when the row carries
    an explicit IVA tagging, else ``gross_amount``) across all observations for
    that casilla.

    ``source_jurisdiction`` is retained on the observation for provenance and is
    ``"ES"`` by construction: a foreign or unresolved jurisdiction is segregated
    into an issue before an observation is ever emitted.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    gross_amount: Decimal = Field(ge=Decimal("0"))
    taxable_base_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    filing_date: date
    source_jurisdiction: CountryCodeAlpha2


class ImpatriadoIncomeLedgerAggregation(
    LedgerAggregationResultBase[ImpatriadoIncomeObservation, ImpatriadoIncomeLedgerAggregationIssue],
):
    """Annual Spanish-source income observations for one Modelo 151 ejercicio.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None


def aggregate_impatriado_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> ImpatriadoIncomeLedgerAggregation:
    """Load the transaction catalogue and aggregate annual impatriado Spanish-source income.

    When no protocol-compatible repository override is supplied, this loader uses
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` scoped to
    ``bucket_id``.

    Returns an :class:`ImpatriadoIncomeLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    # Only the in-window ejercicio subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``. Non-annual periods fall back to
    # the unfiltered load so the aggregation's own period validation still
    # raises the same error.
    if period.kind is not PeriodKind.ANNUAL:
        return aggregate_impatriado_income_ledger(repository.load(), bucket_id=bucket_id, period=period)
    partition = repository.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_impatriado_income_ledger(partition.in_window, bucket_id=bucket_id, period=period)
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_impatriado_income_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
) -> ImpatriadoIncomeLedgerAggregation:
    """Aggregate INCOMING Spanish-source income into Modelo 151 ``impatriado.base-liquidable-general``.

    Applies the impatriado source scope over the FULL ejercicio (Jan 1 to Dec 31
    of ``period.filing_year``): only INCOMING, EUR-denominated rows whose declared
    ``source_jurisdiction`` resolves to ``ES`` fold into the base. Foreign-source
    and jurisdiction-unresolved rows are segregated into
    :attr:`ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED`
    issues rather than silently entering (or silently dropping from) the base.

    Args:
        transactions: The :class:`TransactionCatalogue` to aggregate.
        bucket_id: Bucket identifier carried through to provenance so the
            aggregation cannot be silently misattributed.
        period: The annual :class:`Period` whose year anchors the window.

    Returns an :class:`ImpatriadoIncomeLedgerAggregation` for the ejercicio.
    ``period`` must be the annual period.
    """
    if period.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )
    # The one boundary authority, not a second derivation of it: the repository
    # partition above already selects on ``period.start_date``/``period.end_date``,
    # and this filter re-checks the rows that partition returned. Deriving the
    # same span a second time from the calendar year would make the two agree by
    # coincidence rather than by construction.
    window_start = period.start_date
    window_end = period.end_date

    observations: list[ImpatriadoIncomeObservation] = []
    issues: list[ImpatriadoIncomeLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_impatriado_income_transaction(
            transaction,
            window_start=window_start,
            window_end=window_end,
        )
        if outcome is None:
            continue
        if isinstance(outcome, ImpatriadoIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _impatriado_base_casilla_aggregation(period, observations)
    return ImpatriadoIncomeLedgerAggregation(
        modelo=Modelo.M151.value,
        period=period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_impatriado_income_transaction(
    transaction: Transaction,
    *,
    window_start: date,
    window_end: date,
) -> ImpatriadoIncomeObservation | ImpatriadoIncomeLedgerAggregationIssue | None:
    """Filter one ledger transaction against the impatriado Spanish-source income scope.

    Returns an :class:`ImpatriadoIncomeObservation` for an eligible ES-source
    receipt, an :class:`ImpatriadoIncomeLedgerAggregationIssue` for a row that
    fails a gate (currency, source-jurisdiction segregation, personal, window),
    or ``None`` for a row this base pipeline does not own (OUTGOING / internal
    transfer / operator-excluded).

    The source-jurisdiction gate is the load-bearing art. 93.2 scope: it runs
    BEFORE the amount/eligibility gates so a foreign-source or unresolved row is
    always segregated as a typed issue and can never be silently admitted or
    silently dropped.
    """
    transaction_id = transaction.transaction_id

    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        # Operator reviewed and deliberately excluded this row from filing.
        return None
    if transaction.direction is not TransactionDirection.INCOMING:
        # Only INCOMING income folds into the impatriado base. OUTGOING and
        # internal-transfer rows are out of scope for the base.
        return None
    if is_non_eur_without_conversion(transaction):
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for impatriado income",
        )

    # art. 93.2 source-scope gate (art. 25.1.f TRLIRNR segregation). The
    # impatriado base admits ONLY Spanish-source income. A None jurisdiction is
    # an unresolved provenance, NOT a resident-general ES default: it fails loud
    # as a segregation issue (no-silent-under-declaration).
    declared_jurisdiction = transaction.source_jurisdiction
    if declared_jurisdiction is None:
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED,
            detail=(
                "source_jurisdiction is unresolved (None) on an impatriado income row; "
                "art. 93.2 LIRPF admits only Spanish-source income into the base liquidable "
                "general and an unresolved jurisdiction is never coerced to ES"
            ),
            rejected_source_jurisdiction=None,
        )
    normalized_jurisdiction = declared_jurisdiction.strip().upper()
    if normalized_jurisdiction != _SPANISH_SOURCE_JURISDICTION:
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED,
            detail=(
                f"source_jurisdiction {normalized_jurisdiction!r} is foreign-source; "
                "art. 93.2 LIRPF / art. 25.1.f TRLIRNR segregate it out of the impatriado "
                "base liquidable general (taxed by IRNR scope rules, not the art. 8 worldwide base)"
            ),
            rejected_source_jurisdiction=normalized_jurisdiction,
        )

    proportion = _impatriado_income_proportion(transaction)
    if proportion is None:
        reason = (
            ImpatriadoIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else ImpatriadoIncomeLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=reason,
            detail=(
                f"business classification {transaction.business_classification.value!r} cannot feed the impatriado base"
            ),
        )
    # Use the EUR projection after rejecting unconverted non-EUR rows above, so a
    # converted foreign-currency receipt contributes its EUR equivalent while a
    # domestic row retains its raw amount (mirrors the expense pipeline's
    # ``effective_eur_amount`` usage in ``_renta_ledger.py``).
    gross_amount = effective_eur_amount(transaction) * proportion

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if not (window_start <= filing_date <= window_end):
        return ImpatriadoIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=ImpatriadoIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the annual impatriado income window",
        )

    # Scaled by the SAME proportion the gross above carries, never a second
    # decision. The two figures describe one receipt, and since
    # ``_computable_impatriado_income_amount`` PREFERS the base when it is
    # present, a rule that divided the base alone would silently declare a
    # fraction of an income the gross reported whole.
    # ``transaction.taxable_base`` is native-currency (see
    # ``domain.transactions.tests.test_gross_invariant``), so the EUR-equivalent
    # accessor applies the same fx_rate projection the gross above received.
    taxable_base_amount: Decimal | None = effective_eur_taxable_base(transaction)
    if taxable_base_amount is not None:
        taxable_base_amount *= proportion

    return ImpatriadoIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=_TARGET_CASILLA_IMPATRIADO_BASE,
        gross_amount=gross_amount,
        taxable_base_amount=taxable_base_amount,
        filing_date=filing_date,
        source_jurisdiction=_SPANISH_SOURCE_JURISDICTION,
    )


def _impatriado_income_proportion(transaction: Transaction) -> Decimal | None:
    """Return the share of one row that folds into the impatriado base, or ``None``.

    The single proportion decision for the row: every money figure the
    observation carries is scaled by this one value, so the gross and the
    taxable base cannot disagree about how much of the receipt the base admits.

    The impatriado base admits both ``trabajo`` (rendimientos del trabajo — the
    predominant Beckham base, the class the M130 income pipeline routes OUT) and
    ``actividad_economica`` income at their full magnitude; any other row is
    admitted only through its business proportion, so a genuinely personal
    transfer contributes nothing.

    Admitting a categorised row whole is the legally correct answer to a MIXED
    classification, not merely a convenience. Art. 93.2 LIRPF determines the
    impatriado's deuda tributaria "con arreglo a las normas establecidas en el
    texto refundido de la Ley del Impuesto sobre la Renta de no Residentes,
    para las rentas obtenidas sin mediación de establecimiento permanente", and
    TRLIRNR art. 24.1 (RDLeg 5/2004, BOE-A-2004-4527) fixes that base as "su
    importe íntegro ... sin que sean de aplicación los porcentajes
    multiplicadores ni las reducciones". A usage percentage applied to an
    ingreso is exactly such a porcentaje multiplicador, so the impatriado base
    admits the receipt undivided. Resident IRPF agrees from the other side:
    LIRPF art. 29.2 confines partial affectation to "elementos patrimoniales",
    reaching the rendimiento through those assets' gastos (art. 28.1), and
    nothing in arts. 27-30 divides an INGRESO by a usage percentage.
    """
    if has_employment_irpf_category(
        transaction.irpf_category,
        direction=transaction.direction,
    ) or has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        # The explicit IRPF income category is the authoritative eligibility gate
        # for the impatriado base.
        return Decimal("1")
    return business_proportion(transaction.business_classification, transaction.business_pct)


def _computable_impatriado_income_amount(observation: ImpatriadoIncomeObservation) -> Decimal:
    """Return the fiscally computable ingreso for one observation.

    IVA-exclusive ``taxable_base_amount`` when the row carries an explicit IVA
    tagging, falling back to ``gross_amount`` when no base is declared — the same
    ingresos-íntegros convention the M130 / M100 income aggregation uses, so the
    projection and the binding resolver agree per the one-aggregation-path
    discipline.
    """
    if observation.taxable_base_amount is not None:
        return observation.taxable_base_amount
    return observation.gross_amount


def _impatriado_base_casilla_aggregation(
    period: Period,
    observations: Sequence[ImpatriadoIncomeObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=Modelo.M151.value,
        period=period,
        amount_fn=_computable_impatriado_income_amount,
    )


__all__ = [
    "ImpatriadoIncomeLedgerAggregation",
    "ImpatriadoIncomeLedgerAggregationIssue",
    "ImpatriadoIncomeLedgerAggregationIssueReason",
    "ImpatriadoIncomeObservation",
    "aggregate_impatriado_income_ledger",
    "aggregate_impatriado_income_ledger_from_repositories",
]
