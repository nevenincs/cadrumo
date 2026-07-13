"""Repository-backed IVA observation projection from ledger catalogues.

This module classifies bucket-local
:class:`~domain.transactions.TransactionCatalogue` rows into typed
:class:`~domain.calculations.registry.IvaLedgerObservation` records and
binding-ready totals. The source-mesh resolver in :mod:`~._modelo_bindings`
then applies the target
:class:`~domain.calculations.registry.ModeloRevision`, resolves
``ledger_iva_aggregation`` bindings, and surfaces source diagnostics for ledger
rows that no declared binding consumes.

When the bucket's cross-period prorrata register resolves an active
``general`` provisional percentage for the filing year, the aggregation result
carries :class:`IvaLedgerProrrataApportionment`. The binding resolver applies
that percentage only to deducible IVA cuota bindings; bases and output IVA
cuotas stay unapportioned.

The repository-backed entry point constructs a
:class:`~domain.transactions.TransactionCatalogueRepository` for the active
bucket when none is supplied. Pre-classified callers can use
:class:`IvaLedgerCandidate` and :func:`aggregate_iva_ledger_candidate_bindings`
to run the same validation and registry binding path.

See Also:
    :mod:`~domain.prorrata_register`
        Per-ejercicio carry home for the provisional percentage consumed by
        the IVA ledger apportionment.
    :class:`~application.aggregation._modelo_bindings.LedgerIvaAggregationSourceResolver`
        Source-mesh adapter that calls this projection and records prorrata
        apportionment provenance.
    :mod:`~application.aggregation.tests.test_iva_ledger_prorrata_apportionment`
        Regression coverage proving the active provisional percentage reduces
        deducible cuotas without reducing bases.
    :mod:`~._renta_ledger`, :mod:`~._renta_income_ledger`, :mod:`~._renta_gasto_ledger`
        Sibling Renta ledger projections.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_serializer, field_validator, model_validator

from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind, Period, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n import tr
from ...domain.calculations.registry import (
    BindingId,
    IvaLedgerObservation,
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
)
from ...domain.iva import (
    EUMemberState,
    InputClassification,
    InvoiceKind,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaRateKind,
    IvaRateNotFoundError,
    ProrrataInputError,
    ProrrataReference,
    deductible_percentage_for,
    derive_flow_for_classification,
    lookup_rate,
    validate_prorrata_reference,
)
from ...domain.prorrata_register import ProrrataRegister, ProrrataRegisterRepositoryProtocol
from ...domain.transactions import (
    BusinessClassification,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
)
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import is_non_eur_without_conversion
from ._errors import AggregationValidationError, t

_LedgerId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]

_RATE_KIND_TO_DOMESTIC_CATEGORY: dict[IvaRateKind, IvaCategory] = {
    IvaRateKind.ZERO: IvaCategory.DOMESTIC_ZERO,
    IvaRateKind.SUPER_REDUCED: IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    IvaRateKind.REDUCED: IvaCategory.DOMESTIC_REDUCED_10,
    IvaRateKind.GENERAL: IvaCategory.DOMESTIC_GENERAL_21,
}
_HUNDRED = Decimal("100")


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations.

    The first five values are shared with
    :class:`~application.aggregation._renta_ledger.RentaLedgerAggregationIssueReason`
    through :mod:`~application.aggregation._shared_issue_reasons` so cross-ledger telemetry can
    group upstream filter rejections under one key. The remaining values
    are IVA-specific.
    """

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    UNSUPPORTED_IVA_RATE = "unsupported_iva_rate"
    MISSING_EUR_TAX_SUBSTRATE = "missing_eur_tax_substrate"
    INVALID_PRORRATA_REFERENCE = "invalid_prorrata_reference"
    UNSUPPORTED_IVA_CATEGORY = "unsupported_iva_category"
    MISSING_COUNTERPARTY_EU_MEMBER_STATE = "missing_counterparty_eu_member_state"
    DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION = "domestic_counterparty_on_intra_community_transaction"
    EU_MEMBER_STATE_ON_EXPORT_TRANSACTION = "eu_member_state_on_export_transaction"
    CASH_ACCOUNTING_EXCLUDED_CATEGORY = "cash_accounting_excluded_category"


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class ProrrataLedgerReference(BaseModel):
    """Bucket-local ledger row pointer to a legal IVA prorrata reference."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    reference: ProrrataReference
    base_amount: Decimal = Field(..., ge=Decimal("0"))
    input_iva_amount: Decimal = Field(..., ge=Decimal("0"))


class IvaLedgerSectorApportionment(BaseModel):
    """Per-sector prorrata apportionment for a sectores-diferenciados bucket.

    Under LIVA arts. 9.1.c / 101 a taxpayer with differentiated sectors applies
    the deduction regime separately per sector. Each declared sector carries its
    own provisional ``percentage`` and its own ``regime`` (a sector may run
    general while another runs especial); the sector-aware binding resolver
    applies THIS sector's apportionment to every deducible cuota whose
    observation carries the matching ``sector_id``.

    See Also:
        :class:`~domain.prorrata_register.SectorDefinition`
            Operator-declared sector this apportionment resolves for.
    """

    model_config = _STRICT_FROZEN

    sector_id: str = Field(min_length=1, max_length=64)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=_HUNDRED)
    regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL


class IvaLedgerProrrataApportionment(BaseModel):
    """Prorrata percentage applied to deducible ledger IVA cuotas.

    Under ``regime == GENERAL`` (LIVA art. 104) the single ``percentage`` is
    applied to every deducible cuota binding. Under ``regime == ESPECIAL``
    (LIVA art. 106) ``percentage`` is the general percentage that applies only
    to the COMMON-use inputs; exclusively-deductible inputs deduct in full and
    exclusively-non-deductible inputs deduct nothing, routed per the
    observation's ``input_classification``.

    When ``sector_apportionments`` is non-empty (LIVA arts. 9.1.c / 101), the
    bucket is sectorized: the top-level ``percentage`` / ``regime`` describe the
    COMMON-use apportionment (art. 104.Dos common percentage, for inputs with no
    ``prorrata_sector_id``), and each :class:`IvaLedgerSectorApportionment`
    describes one declared sector. Empty ``sector_apportionments`` is the
    whole-entity register (byte-identical to the pre-sectores behaviour).

    See Also:
        :class:`~core.ProrrataProvisionalProvenance`
            Regulated source of the provisional percentage carried on this
            apportionment.
        :func:`resolve_iva_ledger_binding_values`
            Applies the percentage after registry selector resolution.
    """

    model_config = _STRICT_FROZEN

    percentage: Decimal = Field(..., ge=Decimal("0"), le=_HUNDRED)
    provenance: ProrrataProvisionalProvenance
    regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL
    source_observation_ref: str | None = Field(default=None, min_length=1)
    authorisation_reference: str | None = Field(default=None, min_length=1)
    sector_apportionments: tuple[IvaLedgerSectorApportionment, ...] = ()


class AnnualDeducibleTotalsByRegime(BaseModel):
    """The ejercicio's whole-year deducible IVA cuota under both prorrata regimes.

    The settlement input to the LIVA art. 103.Dos.2 +10% mandatory-especial
    check (``build_prorrata_especial_mandatory_advisory``): art. 103.Dos.2 makes
    prorrata especial obligatory when the deducción under the general regime
    exceeds the deducción under the especial regime by ten percent or more.
    ``deduction_under_general`` is mechanically derivable for any bucket (art. 104
    applies one whole-entity percentage), so it is always honest; the especial
    total (art. 106 per-input classification) is honest only when the register
    regime is ESPECIAL, or when every deducible soportado row of the ejercicio
    carries a declared ``input_classification`` — ``unclassified_deducible_count``
    records how many deducible soportado observations are still unclassified, so
    the caller can decide whether the especial total is honestly computable or the
    filer must first classify.

    See Also:
        :func:`compute_annual_deducible_totals_by_regime`
            Builds this record from one annual observation aggregation and two
            apportionment passes.
    """

    model_config = _STRICT_FROZEN

    deduction_under_general: Decimal = Field(..., ge=Decimal("0"))
    deduction_under_especial: Decimal = Field(..., ge=Decimal("0"))
    unclassified_deducible_count: int = Field(..., ge=0)
    regime: ProrrataRegisterRegime


class IvaLedgerInputKind(StrEnum):
    """Business role of a pre-classified IVA ledger candidate.

    ``ADJUSTMENT`` rows may carry negative bases or cuotas because
    rectification and regularisation entries reverse or correct prior
    operations. The registry consumes the resulting signed observation;
    the model keeps the adjustment axis visible at the application
    boundary where source provenance still exists.
    """

    ORDINARY_OPERATION = "ordinary_operation"
    ADJUSTMENT = "adjustment"


class IvaLedgerCandidate(BaseModel):
    """One pre-classified ledger line for generic IVA aggregation.

    This is the application hand-off shape for IVA facts that cannot be
    inferred safely from a bank transaction direction plus a rate:
    exenciones, no-sujetas, recargo de equivalencia, intra-community
    reverse-charge operations, imports/exports, and explicit
    adjustments. Upstream classifiers must supply the authoritative IVA
    category, rate kind, and flow direction before this layer creates a
    registry-ready :class:`IvaLedgerObservation`.
    """

    model_config = _STRICT_FROZEN

    ledger_id: _LedgerId
    transaction_date: date
    category: IvaCategory
    exemption_article: IvaExemptionArticle | None = None
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal
    input_kind: IvaLedgerInputKind = IvaLedgerInputKind.ORDINARY_OPERATION
    prorrata_reference_id: _LedgerId | None = None
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE

    @model_validator(mode="after")
    def _enforce_exemption_article_category(self) -> IvaLedgerCandidate:
        if self.exemption_article is not None and self.category is not IvaCategory.DOMESTIC_EXEMPT:
            raise AggregationValidationError(
                t("aggregation.iva_ledger.errors.unsupported_iva_category"),
                context={
                    "ledger_id": self.ledger_id,
                    "category": self.category.value,
                    "exemption_article": self.exemption_article.value,
                },
            )
        return self


class IvaLedgerAggregation(BaseModel):
    """IVA observations produced from one bucket-local transaction catalogue.

    ``out_of_window_summary`` is only populated by repository-backed date
    partitions. Full-catalogue aggregation continues to emit row-level issues
    because every transaction is already loaded for classification.
    """

    model_config = _STRICT_FROZEN

    period: Period
    observations: Sequence[IvaLedgerObservation] = Field(default_factory=tuple)
    prorrata_references: Sequence[ProrrataLedgerReference] = Field(default_factory=tuple)
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None
    issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)
    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    # Ledger ids of operator-tagged LIVA art. 104.Tres judgment exclusions
    # (foreign PE, non-habitual inmobiliario/financiero). The prorrata annual
    # volume rollup skips these on the ledger side so the reconciliation does
    # not count operations the law removes from both terms of the ratio. The
    # operations' own IVA cuota observations are unaffected and still aggregate.
    art_104_tres_excluded_ledger_ids: tuple[str, ...] = ()

    @field_validator("observations")
    @classmethod
    def _freeze_observations(cls, value: Sequence[IvaLedgerObservation]) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_validator("art_104_tres_excluded_ledger_ids")
    @classmethod
    def _freeze_excluded_ledger_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)

    @field_validator("prorrata_references")
    @classmethod
    def _freeze_prorrata_references(
        cls,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[IvaLedgerAggregationIssue]) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[IvaLedgerObservation],
    ) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_serializer("prorrata_references")
    def _serialize_prorrata_references(
        self,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_iva_ledger_observations_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol | None = None,
) -> IvaLedgerAggregation:
    """Load the bucket-local transaction catalogue and project IVA observations.

    Returns an :class:`IvaLedgerAggregation`.

    See Also:
        :class:`~adapters.persistence.profile.prorrata_register.ProrrataRegisterRepository`
            Repository consulted for the active general-prorrata provisional
            percentage when no explicit repository is supplied.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    prorrata_apportionment = _active_prorrata_apportionment(
        bucket_id=bucket_id,
        ejercicio=period.filing_year,
        prorrata_register_repository=prorrata_register_repository,
    )
    # Only the in-window subset is decrypted and classified. Out-of-window
    # catalogue rows come from the plaintext date index and are reported
    # uniformly as ``OUTSIDE_PERIOD`` because decrypted-field gates cannot run
    # for those rows. A period with no calendar span falls back to the
    # unfiltered load.
    if not period.has_date_span():
        return aggregate_iva_ledger_observations(
            repository.load(),
            period=period,
            prorrata_apportionment=prorrata_apportionment,
        )
    partition = repository.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_iva_ledger_observations(
        partition.in_window,
        period=period,
        prorrata_apportionment=prorrata_apportionment,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def validate_iva_ledger_observation(candidate: IvaLedgerCandidate) -> IvaLedgerObservation:
    """Validate a pre-classified IVA candidate and return an :class:`IvaLedgerObservation`.

    The validator does not re-classify the operation and does not derive
    IVA from the base. It only blocks sentinel categories that are not
    declarable ledger facts; the category, rate, and flow axes must have
    been resolved upstream from invoice/operation evidence.
    """
    if candidate.category in {IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE}:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": candidate.ledger_id,
                "category": candidate.category.value,
            },
        )
    return IvaLedgerObservation(
        ledger_id=candidate.ledger_id,
        transaction_date=candidate.transaction_date,
        category=candidate.category,
        exemption_article=candidate.exemption_article,
        rate_kind=candidate.rate_kind,
        flow_direction=candidate.flow_direction,
        base_amount=candidate.base_amount,
        iva_amount=candidate.iva_amount,
        prorrata_reference_id=candidate.prorrata_reference_id,
        cash_accounting_treatment=candidate.cash_accounting_treatment,
    )


def validate_iva_ledger_observations(candidates: Iterable[IvaLedgerCandidate]) -> tuple[IvaLedgerObservation, ...]:
    """Validate every pre-classified IVA candidate in input order.

    Returns a tuple of :class:`IvaLedgerObservation` instances.
    """
    return tuple(validate_iva_ledger_observation(candidate) for candidate in candidates)


def aggregate_iva_ledger_candidates(
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
) -> IvaLedgerAggregation:
    """Project pre-classified IVA candidates into period-scoped observations.

    This path complements :func:`aggregate_iva_ledger_observations`,
    which remains the domestic-rate projection from bank
    transactions. Pre-classified candidates are required for non-domestic
    IVA and adjustments because those axes cannot be recovered from a
    transaction amount or direction without guessing.

    Returns an :class:`IvaLedgerAggregation` carrying the accepted
    observations and any period-exclusion issues.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    issues: list[IvaLedgerAggregationIssue] = []
    for candidate in candidates:
        if not resolved_period.contains(candidate.transaction_date):
            issues.append(
                IvaLedgerAggregationIssue(
                    transaction_id=candidate.ledger_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(f"transaction date {candidate.transaction_date.isoformat()} is outside {resolved_period}"),
                ),
            )
            continue
        observations.append(validate_iva_ledger_observation(candidate))
    return IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        issues=tuple(issues),
    )


def aggregate_iva_ledger_candidate_bindings(
    revision: ModeloRevision,
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> dict[BindingId, Decimal]:
    """Validate pre-classified candidates and resolve registry bindings.

    Args:
        revision: The :class:`ModeloRevision` used to resolve binding values.
        candidates: Pre-classified :class:`IvaLedgerCandidate` rows to project
            into engine binding channels.
        period: The aggregation :class:`Period` whose date range bounds the
            candidate set.
        prorrata_apportionment: Optional active general-prorrata percentage to
            apply to deducible IVA cuota bindings after selector resolution.
    """
    aggregation = aggregate_iva_ledger_candidates(candidates, period=period)
    if aggregation.issues:
        first = aggregation.issues[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.candidate_outside_period"),
            context={
                "ledger_id": first.transaction_id,
                "reason": first.reason.value,
                "detail": first.detail,
            },
        )
    unsupported = unsupported_ledger_iva_observations(revision, aggregation.observations)
    if unsupported:
        first = unsupported[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": first.ledger_id,
                "category": first.category.value,
                "rate_kind": first.rate_kind.value,
                "flow_direction": first.flow_direction.value,
                "revision_id": revision.id,
            },
        )
    return resolve_iva_ledger_binding_values(
        revision,
        aggregation.observations,
        prorrata_apportionment=prorrata_apportionment,
    )


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> IvaLedgerAggregation:
    """Project classified ledger transaction tax facts into an :class:`IvaLedgerAggregation`.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        period: Filing period as a typed :class:`Period` instance.
        prorrata_apportionment: Optional active general-prorrata percentage to
            apply later to deducible IVA cuota binding values.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    prorrata_references: list[ProrrataLedgerReference] = []
    issues: list[IvaLedgerAggregationIssue] = []
    art_104_tres_excluded_ledger_ids: list[str] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
            # Operator reviewed and deliberately excluded this row from filing
            # (a final disposition): omit it silently — no observation, no gate
            # issue. The exclusion is an explicit, recorded operator decision,
            # not an unclassified row that should nag with a "classify me" advisory.
            continue
        outcome = _classify_iva_transaction(transaction, resolved_period=resolved_period)
        if outcome.gate_issue is not None:
            issues.append(outcome.gate_issue)
            continue
        if outcome.prorrata_issue is not None:
            issues.append(outcome.prorrata_issue)
        if outcome.prorrata_reference is not None:
            prorrata_references.append(outcome.prorrata_reference)
        observations.extend(outcome.observations)
        # LIVA art. 104.Tres: an operator-declared judgment exclusion removes the
        # operation from BOTH terms of the prorrata ratio. The IVA cuota
        # observations above still aggregate (the operation is a real taxable
        # supply); only the prorrata annual volume rollup skips it, keyed by the
        # ledger id recorded here.
        if transaction.art_104_tres_exclusion is not None:
            art_104_tres_excluded_ledger_ids.append(transaction.transaction_id)
    return IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        prorrata_references=tuple(prorrata_references),
        prorrata_apportionment=prorrata_apportionment,
        issues=tuple(issues),
        art_104_tres_excluded_ledger_ids=tuple(art_104_tres_excluded_ledger_ids),
    )


def resolve_iva_ledger_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
    *,
    prorrata_apportionment: IvaLedgerProrrataApportionment | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve IVA ledger bindings, applying general-prorrata to deducible cuotas only.

    Args:
        revision: The :class:`ModeloRevision` whose IVA ledger bindings are
            resolved.
        observations: Typed :class:`IvaLedgerObservation` rows to aggregate.
        prorrata_apportionment: Optional
            :class:`IvaLedgerProrrataApportionment` applied only to deducible
            cuota bindings.

    Under ``regime == GENERAL`` the single provisional percentage multiplies
    every deducible cuota binding (LIVA art. 104). Under ``regime == ESPECIAL``
    the deducible cuota is routed per the observation's ``input_classification``
    (LIVA art. 106.Uno: exclusively-deductible 100%, exclusively-non-deductible
    0%, common at the general percentage) by
    :func:`_apply_especial_apportionment`; the general-regime code path is
    unchanged.

    See Also:
        :func:`~domain.calculations.registry.resolve_ledger_iva_aggregation_binding_values`
            Registry selector resolver that produces the unapportioned binding
            values before this wrapper applies prorrata.
        :class:`~domain.prorrata_register.ProrrataRegisterEntry`
            Source record for the active provisional percentage represented by
            :class:`IvaLedgerProrrataApportionment`.
    """
    observations = tuple(observations)
    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    if prorrata_apportionment is None:
        return binding_values
    if prorrata_apportionment.sector_apportionments:
        # Sectores diferenciados (LIVA arts. 9.1.c / 101): route each input to
        # its sector's percentage; common-use (no sector) at art. 104.Dos.
        return _apply_sector_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
        )
    if prorrata_apportionment.regime is ProrrataRegisterRegime.ESPECIAL:
        return _apply_especial_apportionment(
            revision,
            observations,
            binding_values,
            prorrata_apportionment,
        )
    # GENERAL regime — byte-identical to the pre-especial behaviour.
    if prorrata_apportionment.percentage == _HUNDRED:
        return binding_values
    multiplier = prorrata_apportionment.percentage / _HUNDRED
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    return {
        binding_id: value * multiplier if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _apply_especial_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per LIVA art. 106 prorrata especial.

    Each deducible cuota binding value is recomputed as the sum, over the
    per-classification partitions of ``observations``, of the partition's
    canonically-resolved binding value weighted by that classification's
    art. 106 deductible percentage (:func:`~domain.iva.deductible_percentage_for`):
    exclusively-deductible at 100%, exclusively-non-deductible at 0%, and
    common-use (and unclassified inputs, the mixed-use default) at the
    ``apportionment.percentage`` general percentage. Non-deducible bindings
    (output cuotas, bases, recargo) keep their unapportioned aggregate.

    The partitions are resolved through the SAME canonical registry resolver
    the general path uses (:func:`~domain.calculations.registry.resolve_ledger_iva_aggregation_binding_values`),
    so especial reuses one aggregation path rather than forking selector logic.
    An all-common (or wholly-unclassified) especial bucket therefore reduces to
    the general-percentage result exactly.
    """
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    general_percentage = apportionment.percentage
    partitions: dict[InputClassification, list[IvaLedgerObservation]] = {
        classification: [] for classification in InputClassification
    }
    for observation in observations:
        classification = observation.input_classification or InputClassification.COMMON
        partitions[classification].append(observation)
    apportioned: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for classification, partition_observations in partitions.items():
        if not partition_observations:
            continue
        multiplier = deductible_percentage_for(classification, general_percentage) / _HUNDRED
        if multiplier == 0:
            # exclusively-non-deductible: contributes nothing to any deducible cuota.
            continue
        partition_values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
        for binding_id in deducible_binding_ids:
            apportioned[binding_id] += partition_values.get(binding_id, Decimal("0")) * multiplier
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _apportioned_deducible_cuota(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    *,
    percentage: Decimal,
    regime: ProrrataRegisterRegime,
    deducible_binding_ids: frozenset[BindingId],
) -> dict[BindingId, Decimal]:
    """Return only the deducible-cuota binding contributions for one observation set.

    Applies the observation set's regime at ``percentage``: ``GENERAL`` multiplies
    every deducible cuota by ``percentage`` (LIVA art. 104); ``ESPECIAL`` routes
    each deducible cuota per the observation's ``input_classification`` (LIVA
    art. 106.Uno reglas 100%/0%/general), with ``percentage`` as the common
    (regla 3.ª) percentage. Both branches resolve through the SAME canonical
    registry resolver, so one aggregation path drives every regime. This is the
    per-partition primitive the sectores-diferenciados routing composes over each
    sector.
    """
    result: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    if regime is ProrrataRegisterRegime.ESPECIAL:
        partitions: dict[InputClassification, list[IvaLedgerObservation]] = {
            classification: [] for classification in InputClassification
        }
        for observation in observations:
            classification = observation.input_classification or InputClassification.COMMON
            partitions[classification].append(observation)
        for classification, partition_observations in partitions.items():
            if not partition_observations:
                continue
            multiplier = deductible_percentage_for(classification, percentage) / _HUNDRED
            if multiplier == 0:
                continue
            partition_values = resolve_ledger_iva_aggregation_binding_values(revision, partition_observations)
            for binding_id in deducible_binding_ids:
                result[binding_id] += partition_values.get(binding_id, Decimal("0")) * multiplier
        return result
    # GENERAL regime: a single multiplier over the whole observation set.
    multiplier = percentage / _HUNDRED
    partition_values = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    for binding_id in deducible_binding_ids:
        result[binding_id] = partition_values.get(binding_id, Decimal("0")) * multiplier
    return result


def _apply_sector_apportionment(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    binding_values: dict[BindingId, Decimal],
    apportionment: IvaLedgerProrrataApportionment,
) -> dict[BindingId, Decimal]:
    """Route deducible cuota bindings per sector (LIVA arts. 9.1.c / 101).

    Partitions ``observations`` by ``prorrata_sector_id`` and recomputes each
    deducible cuota binding as the sum, over the partitions, of that sector's
    :func:`_apportioned_deducible_cuota` contribution (each sector applies its
    own percentage and regime). An input with no sector — or one referencing a
    sector not present in ``sector_apportionments`` — falls to the COMMON-use
    apportionment: the top-level ``apportionment.percentage`` / ``regime`` (the
    art. 104.Dos common percentage). Non-deducible bindings keep their
    unapportioned aggregate. Resolution runs through the SAME canonical registry
    resolver, so the sectored path is one more consumer of the single
    aggregation path.
    """
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return binding_values
    by_sector = {sector.sector_id: sector for sector in apportionment.sector_apportionments}
    partitions: dict[str | None, list[IvaLedgerObservation]] = {}
    for observation in observations:
        sector_key = observation.prorrata_sector_id if observation.prorrata_sector_id in by_sector else None
        partitions.setdefault(sector_key, []).append(observation)
    apportioned: dict[BindingId, Decimal] = dict.fromkeys(deducible_binding_ids, Decimal("0"))
    for sector_key, partition_observations in partitions.items():
        if sector_key is None:
            percentage = apportionment.percentage
            regime = apportionment.regime
        else:
            sector = by_sector[sector_key]
            percentage = sector.percentage
            regime = sector.regime
        partition_deducible = _apportioned_deducible_cuota(
            revision,
            partition_observations,
            percentage=percentage,
            regime=regime,
            deducible_binding_ids=deducible_binding_ids,
        )
        for binding_id in deducible_binding_ids:
            apportioned[binding_id] += partition_deducible[binding_id]
    return {
        binding_id: apportioned[binding_id] if binding_id in deducible_binding_ids else value
        for binding_id, value in binding_values.items()
    }


def _active_prorrata_apportionment(
    *,
    bucket_id: str,
    ejercicio: int,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol | None,
) -> IvaLedgerProrrataApportionment | None:
    """Resolve the regime-aware prorrata apportionment for the ejercicio.

    Returns ``None`` when no register entry applies, the entry's regime carries
    no apportionment (``NINGUNA``), or no provisional percentage is resolvable.
    A ``GENERAL`` entry carries the single provisional percentage; an
    ``ESPECIAL`` entry carries the same provisional percentage as the general
    percentage applied to common-use inputs (LIVA art. 106.Uno regla 3.ª),
    with the regime stamped so the binding resolver routes per-input.

    When the register declares a differentiated-sector partition
    (LIVA arts. 9.1.c / 101), the whole-entity (``sector_id = None``) entry is
    the COMMON-use apportionment (art. 104.Dos common percentage) and each
    declared sector's ``(ejercicio, sector_id)`` entry contributes a
    :class:`IvaLedgerSectorApportionment`; a sectorized register therefore also
    requires its common ``sector_id = None`` entry to apportion common-use
    inputs (absent it, no apportionment applies, exactly as for any register
    with no whole-entity entry).
    """
    repository = prorrata_register_repository or ProrrataRegisterRepository(bucket_id=bucket_id)
    register = repository.load()
    base = _sector_scoped_apportionment(register, ejercicio, sector_id=None)
    if base is None:
        return None
    if not register.is_sectorized:
        return base
    sector_apportionments = tuple(
        IvaLedgerSectorApportionment(
            sector_id=sector_id,
            percentage=sector.percentage,
            regime=sector.regime,
        )
        for sector_id in register.sector_ids()
        if (sector := _sector_scoped_apportionment(register, ejercicio, sector_id=sector_id)) is not None
    )
    if not sector_apportionments:
        return base
    return base.model_copy(update={"sector_apportionments": sector_apportionments})


def _sector_scoped_apportionment(
    register: ProrrataRegister,
    ejercicio: int,
    *,
    sector_id: str | None,
) -> IvaLedgerProrrataApportionment | None:
    """Resolve the apportionment for one ``(ejercicio, sector_id)`` register key.

    Returns ``None`` when the key has no apportioning entry (``NINGUNA`` /
    interrupted / absent) or no provisional percentage is resolvable.
    """
    entry = register.entry_for(ejercicio, sector_id=sector_id)
    if entry is None or entry.regime not in (
        ProrrataRegisterRegime.GENERAL,
        ProrrataRegisterRegime.ESPECIAL,
    ):
        return None
    resolution = register.resolve_provisional(ejercicio, sector_id=sector_id)
    if resolution.percentage is None or resolution.provenance is None:
        return None
    return IvaLedgerProrrataApportionment(
        percentage=resolution.percentage,
        provenance=resolution.provenance,
        regime=entry.regime,
        source_observation_ref=entry.source_observation_ref,
        authorisation_reference=entry.authorisation_reference,
    )


def _deducible_cuota_binding_ids(revision: ModeloRevision) -> frozenset[BindingId]:
    ledger_iva_amount_bindings = {
        binding.id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        and getattr(binding.selector, "fact", "iva_amount_sum") == "iva_amount_sum"
    }
    binding_ids: set[BindingId] = set()
    for casilla in revision.casillas:
        if "deducible" not in casilla.section:
            continue
        for binding_id in (casilla.binding, *casilla.alternate_bindings):
            if binding_id is not None and binding_id in ledger_iva_amount_bindings:
                binding_ids.add(binding_id)
    return frozenset(binding_ids)


def _unclassified_deducible_soportado_count(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    deducible_binding_ids: frozenset[BindingId],
) -> int:
    """Count deducible-cuota observations that carry no ``input_classification``.

    A deducible soportado observation is one whose own canonically-resolved
    contribution lands on at least one deducible cuota binding (the registry
    selector decides membership; no category is hard-coded here). An observation
    with no declared ``input_classification`` is one the art. 106 especial total
    cannot honestly route, so the general filer must classify it before the +10%
    check can run. The signal drives the CHECK-vs-PROMPT branch in the settlement
    collector.
    """
    count = 0
    for observation in observations:
        if observation.input_classification is not None:
            continue
        single = resolve_ledger_iva_aggregation_binding_values(revision, (observation,))
        if any(single.get(binding_id, Decimal("0")) != Decimal("0") for binding_id in deducible_binding_ids):
            count += 1
    return count


def compute_annual_deducible_totals_by_regime(
    *,
    bucket_id: str,
    ejercicio: int,
    revision: ModeloRevision,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol | None = None,
) -> AnnualDeducibleTotalsByRegime | None:
    """Compute the ejercicio's deducible IVA cuota under both prorrata regimes.

    The plumbing for the LIVA art. 103.Dos.2 +10% mandatory-especial settlement
    check. Aggregates the ejercicio's annual IVA observations ONCE
    (:func:`aggregate_iva_ledger_observations_from_repositories` over the
    canonical ``0A`` annual :class:`~core.Period`), then resolves
    :func:`resolve_iva_ledger_binding_values` TWICE over the same observations —
    once with a GENERAL-stamped and once with an ESPECIAL-stamped
    :class:`IvaLedgerProrrataApportionment` at the register's resolved percentage
    — and sums the deducible-cuota binding ids under each. One aggregation, two
    apportionment passes through the one canonical resolver
    (``one-aggregation-path-pull-equals-calculate``); no second aggregation
    implementation is introduced.

    Returns ``None`` when no register apportionment resolves for the ejercicio
    (prorrata inapplicable), when the register is sectorized (LIVA arts. 9.1.c /
    101 — the art-103.Dos.2 comparison composes per sector, a named v1 deferral),
    or when the revision declares no deducible cuota bindings. A negative
    deducible total (an adjustment-heavy degenerate case the art-103.Dos.2
    comparison is undefined over) also returns ``None`` so the check stays silent
    rather than crashing on a non-comparable input.

    Args:
        bucket_id: Active bucket whose annual ledger and prorrata register are
            read.
        ejercicio: The filing year whose annual deducible totals are computed.
        revision: The target :class:`ModeloRevision` whose deducible cuota
            bindings are summed.
        transaction_repository: Optional catalogue repository (defaults to the
            active bucket's).
        prorrata_register_repository: Optional register repository (defaults to
            the active bucket's).

    See Also:
        :class:`AnnualDeducibleTotalsByRegime`
            The frozen record returned.
        :func:`~application.calculations.build_prorrata_especial_mandatory_advisory`
            Consumes the two totals to build the +10% advisory.
    """
    period = Period.from_year_and_code(ejercicio, "0A")
    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=transaction_repository,
        prorrata_register_repository=prorrata_register_repository,
    )
    apportionment = aggregation.prorrata_apportionment
    if apportionment is None:
        return None
    if apportionment.sector_apportionments:
        # Sectorized register: the art-103.Dos.2 comparison composes per sector,
        # a named v1 deferral (LIVA arts. 9.1.c / 101). No branch in v1.
        return None
    deducible_binding_ids = _deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return None
    observations = tuple(aggregation.observations)
    general_apportionment = apportionment.model_copy(update={"regime": ProrrataRegisterRegime.GENERAL})
    especial_apportionment = apportionment.model_copy(update={"regime": ProrrataRegisterRegime.ESPECIAL})
    general_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=general_apportionment,
    )
    especial_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=especial_apportionment,
    )
    deduction_under_general = sum(
        (general_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    deduction_under_especial = sum(
        (especial_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    if deduction_under_general < Decimal("0") or deduction_under_especial < Decimal("0"):
        return None
    return AnnualDeducibleTotalsByRegime(
        deduction_under_general=deduction_under_general,
        deduction_under_especial=deduction_under_especial,
        unclassified_deducible_count=_unclassified_deducible_soportado_count(
            revision,
            observations,
            deducible_binding_ids,
        ),
        regime=apportionment.regime,
    )


@dataclass(frozen=True)
class _IvaTransactionOutcome:
    """Per-transaction outcome carrying the typed sinks the orchestrator drains.

    A transaction either fails a pre-observation gate (``gate_issue``
    populated, nothing else) or it survives all pre-gates and produces
    an ``observation``. The observation path may additionally emit a
    ``prorrata_reference`` AND/OR a ``prorrata_issue`` — they are
    independent sinks: an invalid prorrata-reference attaches to the
    issue list, a valid one attaches to the prorrata-references list,
    and either way the observation itself is recorded.
    """

    gate_issue: IvaLedgerAggregationIssue | None = None
    observations: tuple[IvaLedgerObservation, ...] = ()
    prorrata_reference: ProrrataLedgerReference | None = None
    prorrata_issue: IvaLedgerAggregationIssue | None = None


# Categories that never produce a declarable IVA observation: recargo de
# equivalencia (the IVA + RE surcharge is non-deductible acquisition cost for the
# retailer, settled via the supplier) and the unknown/erroneous sentinels.
_NON_DECLARABLE_IVA_CATEGORIES = frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.UNKNOWN,
        IvaCategory.ERRONEOUS_INVOICE,
    },
)

_CASH_ACCOUNTING_EXCLUDED_CATEGORIES = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        IvaCategory.IMPORT_THIRD_COUNTRY,
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        IvaCategory.OPERACION_NO_SUJETA,
    },
)


def _classify_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
) -> _IvaTransactionOutcome:
    """Filter + classify one ledger transaction against the IVA aggregation pipeline.

    Returns an :class:`_IvaTransactionOutcome` carrying the typed
    sinks the orchestrator drains. Each pre-observation gate projects
    to ``gate_issue`` with a typed
    :class:`IvaLedgerAggregationIssueReason`. The observation-eligible
    path constructs the observation and (when present) the prorrata
    reference; an invalid prorrata reference is reported as a
    ``prorrata_issue`` alongside the observation.
    """
    transaction_id = transaction.transaction_id
    ledger_date = transaction.raw.value_date or transaction.raw.booked_date
    operation_date = transaction.cash_accounting_operation_date or ledger_date
    cash_treatment = transaction.cash_accounting_treatment
    if cash_treatment is IvaCashAccountingTreatment.NONE and not resolved_period.contains(operation_date):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                detail=f"transaction date {operation_date.isoformat()} is outside {resolved_period}",
            ),
        )
    if is_non_eur_without_conversion(transaction):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for IVA aggregation",
            ),
        )
    if _has_converted_non_eur_amount(transaction):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE,
                detail=(
                    f"transaction currency {transaction.raw.currency!r} has a converted gross value_in_eur "
                    "but taxable_base/iva_amount remain native-currency facts; IVA aggregation requires "
                    "explicit EUR tax substrate"
                ),
            ),
        )
    flow_direction = _flow_direction_for(transaction.direction)
    if flow_direction is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                detail=f"transaction direction {transaction.direction.value!r} is not an IVA settlement flow",
            ),
        )
    proportionality = _business_proportionality(transaction)
    if proportionality is None:
        reason = (
            IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=reason,
                detail=(
                    f"business classification {transaction.business_classification.value!r} cannot feed IVA aggregation"
                ),
            ),
        )
    iva_category = transaction.iva_category
    if iva_category is not None and iva_category in _NON_DECLARABLE_IVA_CATEGORIES:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY,
                detail=(
                    f"iva_category {iva_category.value!r} does not produce a declarable IVA "
                    "observation (recargo-equivalencia is non-deductible cost; unknown/erroneous are sentinels)"
                ),
            ),
        )
    missing_reason = _missing_tax_fact_reason(transaction)
    if missing_reason is not None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=missing_reason,
                detail=_missing_tax_fact_detail(missing_reason),
            ),
        )
    assert transaction.taxable_base is not None
    assert transaction.iva_amount is not None
    assert transaction.iva_rate is not None
    rate_kind = _iva_rate_kind_for(transaction.iva_rate, on_date=operation_date)
    if rate_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
                detail=f"IVA rate {transaction.iva_rate} is not a canonical substrate IVA rate",
            ),
        )
    base_amount = transaction.taxable_base * proportionality
    iva_amount = transaction.iva_amount * proportionality
    recargo_amount = (transaction.recargo_amount or Decimal("0")) * proportionality

    # Resolve the effective IVA category: explicit override takes priority over
    # the rate-kind-derived domestic category.
    explicit_category = transaction.iva_category
    if explicit_category is not None:
        d5_issue = _validate_intracom_export_counterparty(
            transaction_id=transaction_id,
            category=explicit_category,
            eu_member_state=transaction.counterparty_eu_member_state,
        )
        if d5_issue is not None:
            return _IvaTransactionOutcome(gate_issue=d5_issue)
        effective_category = explicit_category
    else:
        effective_category = _RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind]

    if (
        cash_treatment is not IvaCashAccountingTreatment.NONE
        and effective_category in _CASH_ACCOUNTING_EXCLUDED_CATEGORIES
    ):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EXCLUDED_CATEGORY,
                detail=(
                    f"iva_category {effective_category.value!r} is excluded from the cash-accounting regime "
                    "under Ley 37/1992 art. 163 duodecies"
                ),
            ),
        )

    # Recompute the IVA flow now the effective category is known. The
    # direction-only screen above only rejects non-settlement directions;
    # the canonical flow routes reverse-charge categories
    # (DOMESTIC_REVERSE_CHARGE, INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE)
    # to INVERSION_SUJETO_PASIVO and leaves every other category on its
    # repercutido/soportado direction. ``_invoice_kind_for`` cannot be
    # None here: ``flow_direction`` above already gated unknown directions.
    invoice_kind = _invoice_kind_for(transaction.direction)
    assert invoice_kind is not None
    flow_direction = derive_flow_for_classification(
        category=effective_category,
        invoice_direction=invoice_kind,
    )

    prorrata_reference, prorrata_issue, linked_prorrata_id = _resolve_iva_prorrata_attachment(
        transaction,
        flow_direction=flow_direction,
        operation_date=operation_date,
        base_amount=base_amount,
        iva_amount=iva_amount,
    )
    if cash_treatment is not IvaCashAccountingTreatment.NONE:
        observations = _cash_accounting_observations(
            transaction,
            resolved_period=resolved_period,
            operation_date=operation_date,
            category=effective_category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            proportionality=proportionality,
            full_base_amount=base_amount,
            full_iva_amount=iva_amount,
            linked_prorrata_id=linked_prorrata_id,
        )
        if not observations:
            return _IvaTransactionOutcome(
                gate_issue=IvaLedgerAggregationIssue(
                    transaction_id=transaction_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(
                        "cash-accounting operation date, payment evidence dates, and fallback date "
                        f"are outside {resolved_period}"
                    ),
                ),
            )
        return _IvaTransactionOutcome(
            observations=observations,
            prorrata_reference=prorrata_reference,
            prorrata_issue=prorrata_issue,
        )
    observation = _iva_observation(
        ledger_id=transaction.transaction_id,
        transaction_date=operation_date,
        category=effective_category,
        exemption_article=transaction.exemption_article,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        prorrata_reference_id=linked_prorrata_id,
        input_classification=transaction.input_classification,
        prorrata_sector_id=transaction.prorrata_sector_id,
    )
    return _IvaTransactionOutcome(
        observations=(observation,),
        prorrata_reference=prorrata_reference,
        prorrata_issue=prorrata_issue,
    )


def _iva_observation(
    *,
    ledger_id: str,
    transaction_date: date,
    category: IvaCategory,
    exemption_article: IvaExemptionArticle | None,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    base_amount: Decimal,
    iva_amount: Decimal,
    recargo_amount: Decimal = Decimal("0"),
    prorrata_reference_id: str | None = None,
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE,
    input_classification: InputClassification | None = None,
    prorrata_sector_id: str | None = None,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        category=category,
        exemption_article=exemption_article,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        prorrata_reference_id=prorrata_reference_id,
        cash_accounting_treatment=cash_accounting_treatment,
        input_classification=input_classification,
        prorrata_sector_id=prorrata_sector_id,
    )


def _cash_accounting_observations(
    transaction: Transaction,
    *,
    resolved_period: Period,
    operation_date: date,
    category: IvaCategory,
    rate_kind: IvaRateKind,
    flow_direction: IvaFlowDirection,
    proportionality: Decimal,
    full_base_amount: Decimal,
    full_iva_amount: Decimal,
    linked_prorrata_id: str | None,
) -> tuple[IvaLedgerObservation, ...]:
    observations: list[IvaLedgerObservation] = []
    for payment_date, base_amount, iva_amount, recargo_amount in _cash_accounting_settlement_parts(transaction):
        if not resolved_period.contains(payment_date):
            continue
        observations.append(
            _iva_observation(
                ledger_id=transaction.transaction_id,
                transaction_date=payment_date,
                category=category,
                exemption_article=transaction.exemption_article,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=base_amount * proportionality,
                iva_amount=iva_amount * proportionality,
                recargo_amount=recargo_amount * proportionality,
                prorrata_reference_id=linked_prorrata_id,
                input_classification=transaction.input_classification,
                prorrata_sector_id=transaction.prorrata_sector_id,
            ),
        )
    if resolved_period.contains(operation_date):
        observations.append(
            _iva_observation(
                ledger_id=transaction.transaction_id,
                transaction_date=operation_date,
                category=category,
                exemption_article=transaction.exemption_article,
                rate_kind=rate_kind,
                flow_direction=flow_direction,
                base_amount=full_base_amount,
                iva_amount=full_iva_amount,
                cash_accounting_treatment=transaction.cash_accounting_treatment,
                input_classification=transaction.input_classification,
                prorrata_sector_id=transaction.prorrata_sector_id,
            ),
        )
    return tuple(observations)


def _cash_accounting_settlement_parts(
    transaction: Transaction,
) -> tuple[tuple[date, Decimal, Decimal, Decimal], ...]:
    assert transaction.cash_accounting_operation_date is not None
    assert transaction.taxable_base is not None
    assert transaction.iva_amount is not None
    parts = [
        (
            evidence.payment_date,
            evidence.taxable_base,
            evidence.iva_amount,
            evidence.recargo_amount,
        )
        for evidence in transaction.cash_accounting_payment_evidence
    ]
    paid_base = sum((part[1] for part in parts), Decimal("0"))
    paid_iva = sum((part[2] for part in parts), Decimal("0"))
    paid_recargo = sum((part[3] for part in parts), Decimal("0"))
    recargo_amount = transaction.recargo_amount or Decimal("0")
    remainder = (
        transaction.taxable_base - paid_base,
        transaction.iva_amount - paid_iva,
        recargo_amount - paid_recargo,
    )
    if any(amount > Decimal("0") for amount in remainder):
        fallback_date = date(transaction.cash_accounting_operation_date.year + 1, 12, 31)
        parts.append((fallback_date, *remainder))
    return tuple(sorted(parts, key=lambda part: part[0]))


def _resolve_iva_prorrata_attachment(
    transaction: Transaction,
    *,
    flow_direction: IvaFlowDirection,
    operation_date: date,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> tuple[ProrrataLedgerReference | None, IvaLedgerAggregationIssue | None, str | None]:
    """Resolve the (prorrata-reference, prorrata-issue, linked-id) triple.

    Returns ``(None, None, None)`` when the transaction carries no
    prorrata_reference. Returns ``(None, issue, None)`` when the
    reference fails parsing OR the row is not a supported-input IVA
    row (prorrata only attaches to SOPORTADO flows). Returns
    ``(reference, None, transaction_id)`` for a valid attachment.
    """
    raw_reference = _prorrata_reference_for(
        transaction.prorrata_reference,
        transaction_id=transaction.transaction_id,
    )
    if isinstance(raw_reference, IvaLedgerAggregationIssue):
        return None, raw_reference, None
    if raw_reference is None:
        return None, None, None
    if flow_direction is not IvaFlowDirection.SOPORTADO:
        return (
            None,
            IvaLedgerAggregationIssue(
                transaction_id=transaction.transaction_id,
                reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
                detail="prorrata_reference may only be attached to supported input IVA rows",
            ),
            None,
        )
    return (
        ProrrataLedgerReference(
            transaction_id=transaction.transaction_id,
            transaction_date=operation_date,
            reference=raw_reference,
            base_amount=base_amount,
            input_iva_amount=iva_amount,
        ),
        None,
        transaction.transaction_id,
    )


def _validate_intracom_export_counterparty(
    *,
    transaction_id: str,
    category: IvaCategory,
    eu_member_state: EUMemberState | None,
) -> IvaLedgerAggregationIssue | None:
    """Return a gate issue when the counterparty/category coupling is violated.

    Rules:
    - ``INTRA_COMMUNITY_SUPPLY`` requires a non-ES ``EUMemberState``.
    - Export and export-assimilated categories must carry no ``EUMemberState``.
    """
    if category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
        if eu_member_state is None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_EU_MEMBER_STATE,
                detail="intra-community supply requires a non-ES counterparty EU member state",
            )
        if eu_member_state is EUMemberState.ES:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION,
                detail=tr(
                    "aggregation.iva_ledger.errors.domestic_counterparty_on_intra_community_transaction",
                    default="Spanish counterparties are not valid for intra-community transactions.",
                ),
            )
    if (
        category
        in {
            IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
            IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        }
        and eu_member_state is not None
    ):
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
            detail=tr(
                "aggregation.iva_ledger.errors.eu_member_state_on_export_transaction",
                member_state=eu_member_state.value,
                default=(
                    "Export or export-assimilated operations must not carry an EU member state; got %{member_state}."
                ),
            ),
        )
    return None


def validate_iva_ledger_counterparty_category(transaction: Transaction) -> IvaLedgerAggregationIssue | None:
    """Return the D5 counterparty/category gate :class:`IvaLedgerAggregationIssue` for a ledger transaction."""
    category = transaction.iva_category
    if category is None:
        return None
    return _validate_intracom_export_counterparty(
        transaction_id=transaction.transaction_id,
        category=category,
        eu_member_state=transaction.counterparty_eu_member_state,
    )


def _invoice_kind_for(direction: TransactionDirection) -> InvoiceKind | None:
    """Map a bank :class:`TransactionDirection` onto the invoice-issuance axis.

    ``INCOMING`` money is a sale the autónomo issued (output IVA);
    ``OUTGOING`` money is a purchase the autónomo received (input IVA).
    Returns ``None`` for any direction that is not an IVA settlement
    flow, so the caller can reject it as ``UNSUPPORTED_DIRECTION``.
    """
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None


def _flow_direction_for(direction: TransactionDirection) -> IvaFlowDirection | None:
    """Return the direction-only IVA flow, used as the settlement-flow gate.

    This screens the bank direction before the IVA category is known
    (an ``UNKNOWN``/``UNRESOLVED`` direction is not an IVA settlement
    flow). The final flow that lands on the observation is recomputed
    once the effective :class:`IvaCategory` is resolved via
    :func:`derive_flow_for_classification`, which routes reverse-charge
    categories to :attr:`~domain.iva.IvaFlowDirection.INVERSION_SUJETO_PASIVO` while
    preserving ``REPERCUTIDO``/``SOPORTADO`` for every other category.
    """
    invoice_kind = _invoice_kind_for(direction)
    if invoice_kind is None:
        return None
    return IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO


def _business_proportionality(transaction: Transaction) -> Decimal | None:
    return business_proportion(transaction.business_classification, transaction.business_pct)


def _has_converted_non_eur_amount(transaction: Transaction) -> bool:
    return transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is not None


def _missing_tax_fact_reason(transaction: Transaction) -> IvaLedgerAggregationIssueReason | None:
    reasons = iva_ledger_missing_fact_reasons(transaction)
    return reasons[0] if reasons else None


def iva_ledger_missing_fact_reasons(transaction: Transaction) -> tuple[IvaLedgerAggregationIssueReason, ...]:
    """Return missing IVA fact reasons for a transaction without projecting it.

    Each element is an :class:`IvaLedgerAggregationIssueReason` describing
    one absent required tax fact.
    """
    reasons: list[IvaLedgerAggregationIssueReason] = []
    if transaction.taxable_base is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE)
    if transaction.iva_amount is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT)
    if transaction.iva_rate is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_RATE)
    return tuple(reasons)


def _missing_tax_fact_detail(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    }[reason]


def _prorrata_reference_for(
    reference_id: str | None,
    *,
    transaction_id: str,
) -> ProrrataReference | IvaLedgerAggregationIssue | None:
    if reference_id is None:
        return None
    try:
        return validate_prorrata_reference(reference_id)
    except ProrrataInputError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail=str(exc),
        )


def _iva_rate_kind_for(rate: Decimal, *, on_date: date) -> IvaRateKind | None:
    for kind in _RATE_KIND_TO_DOMESTIC_CATEGORY:
        try:
            rate_record = lookup_rate(EUMemberState.ES, kind, on_date)
        except IvaRateNotFoundError:
            continue
        if rate_record.pct / Decimal("100") == rate:
            return kind
    return None


__all__ = [
    "AnnualDeducibleTotalsByRegime",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerCandidate",
    "IvaLedgerInputKind",
    "IvaLedgerProrrataApportionment",
    "IvaLedgerSectorApportionment",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_candidate_bindings",
    "aggregate_iva_ledger_candidates",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "compute_annual_deducible_totals_by_regime",
    "iva_ledger_missing_fact_reasons",
    "resolve_iva_ledger_binding_values",
    "validate_iva_ledger_counterparty_category",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
]
