"""Read-only Modelo 100/130 projections of the activity-asset register.

Modelo 100 carries effective claims only. Modelo 130 carries what each element
accrued from 1 January to the quarter's end, worked out from its schedule without
recording anything (RIRPF art. 110.1.a); an element on a free method has no
computable accrual, so it contributes its effective claims. Neither creates a
charge. The register is the only route to the activity amortization boxes: a
ledger row in an amortization category is acquisition evidence, withheld when the
register owns it and a blocking note when it does not.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Protocol

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.categories.spending_category_catalogue import amortizable_spending_categories
from ...domain.contribuyente.tax_residence import ResidenceTerritory
from ...domain.modelos.calculation_revision_sources import (
    ACTIVITY_ASSET_CLAIM_REF_PREFIX,
    ACTIVITY_ASSET_SCHEDULE_REF_PREFIX,
)
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    asset_schedule_history,
    current_revisions,
    m100_casilla_id,
    select_effective_claims,
    uncovered_claim_intervals,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS
from ...domain.renta.actividad_asset.errors import ActividadAssetError, ActividadAssetPeriodElapsedError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetBasisStage
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.schedule_walk import (
    M130ElementAccrual,
    M130ElementOutcome,
    free_base_remains,
    m130_register_accruals,
)
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..user_profile.plantilla_media_rows import plantilla_media_years_of
from . import _shared_issue_reasons
from .renta_ledger import resident_territory
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceProvenance
from .source_resolution_operations import source_diagnostics_for

_AGRARIAN_INSTALMENT_SELECTOR: Final[str] = (
    "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras"
)
"""The activities whose instalment is a share of income under RIRPF art. 110.1.c."""

_NOT_A_DECLARED_EXPENSE_ISSUE_REASONS: Final[frozenset[str]] = frozenset(
    {
        _shared_issue_reasons.OUTSIDE_PERIOD,
        _shared_issue_reasons.UNSUPPORTED_DIRECTION,
        _shared_issue_reasons.PERSONAL_TRANSACTION,
        _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE,
    },
)
"""Refusals saying a row is not this period's business expense, so it declares no amortization here."""


class LedgerRentaExpenseTreatment(BaseModel):
    """One ledger-derived Renta expense row weighed against the activity-asset register.

    ``amortization_labelled`` states whether the row's own Renta destination is
    one of the activity amortization casillas
    (:data:`~domain.renta.actividad_asset.claims.M100_AMORTIZATION_CASILLA_IDS`).
    The two Renta expense projections derive it differently -- the annual
    first-slice observation already carries its resolved target casilla, while
    the quarterly gasto row carries only its ledger category -- so each caller
    resolves the flag and this boundary keeps one meaning for it.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int
    deductible_amount: Decimal
    amortization_labelled: bool


class RegisterOwnedAcquisition(BaseModel):
    """One ledger expense row the activity-asset register owns as a capital acquisition.

    The row stays in the ledger as acquisition evidence; what is withheld is its
    contribution to a Renta deductible-expense total, because the acquisition
    price is the amortizable base rather than a current expense (RIS art. 3.2,
    LIS art. 12.1 through LIRPF art. 28.1).
    """

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    transaction_id: TransactionId
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int
    purchase_amount: Decimal | None = None


class ActivityAssetClaimSource(BaseModel):
    """An observation resting on one recorded effective claim."""

    model_config = STRICT_FROZEN_CONFIG

    claim_id: Hex64Str

    @property
    def contributor_source_kind(self) -> str:
        """Name this kind of contributor in provenance."""
        return "activity_asset_claim"

    @property
    def source_ref(self) -> str:
        """Identify the claim in provenance."""
        return f"{ACTIVITY_ASSET_CLAIM_REF_PREFIX}{self.claim_id}"


class ActivityAssetScheduleSource(BaseModel):
    """An observation resting on an element's schedule, with no claim behind it."""

    model_config = STRICT_FROZEN_CONFIG

    schedule_fingerprint: Hex64Str

    @property
    def contributor_source_kind(self) -> str:
        """Name this kind of contributor in provenance."""
        return "activity_asset_schedule"

    @property
    def source_ref(self) -> str:
        """Identify the schedule in provenance."""
        return f"{ACTIVITY_ASSET_SCHEDULE_REF_PREFIX}{self.schedule_fingerprint}"


class ActivityAssetExpenseObservation(BaseModel):
    """One amount of the register projected through an existing Renta expense owner."""

    model_config = STRICT_FROZEN_CONFIG

    source: ActivityAssetClaimSource | ActivityAssetScheduleSource
    modelo: str
    period: str = Field(min_length=2, max_length=2)
    target_casilla_id: CasillaId
    deductible_amount: Decimal = Field(ge=Decimal("0"))


@dataclass(frozen=True, slots=True)
class ActivityAssetProjection:
    """What the register contributes to one calculation, and what it has to say about it."""

    observations: tuple[ActivityAssetExpenseObservation, ...] = ()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()


class _Forecast:
    """The one schedule route, bound to one calculation's authority and profile."""

    def __init__(self, context: CalculationSourceContext, operation: PinnedAuthorityOperation) -> None:
        self._context = context
        self._operation = operation

    def __call__(
        self,
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        """Forecast one element's charge without recording anything."""
        profile = self._context.profile
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=self._operation.revision_for_context(
                "100",
                filing_year=covered_from.year,
                period="0A",
            ),
            authority_generation=self._operation.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=lambda: () if profile is None else plantilla_media_years_of(profile.record),
            legal_reference=self._operation.legal_reference,
            requested_free_amount=requested_free_amount,
        )


def m100_activity_asset_projection(
    history: ActivityAssetHistory,
    *,
    context: CalculationSourceContext,
    period: Period,
    operation: PinnedAuthorityOperation,
    resolver_id: str,
) -> ActivityAssetProjection:
    """Project effective claims into casillas 0208 and 0227, reporting this year's uncovered intervals.

    A gap is reported and never filled: the deduction is not invented, the return
    is not refused, and only the filing year is examined, so a gap of an earlier
    year cannot weigh on a later one.

    Returns:
        The claims' observations and a non-blocking finding per uncovered interval.
    """
    current = current_revisions(history.revisions)
    if not current:
        return ActivityAssetProjection()
    if _foral(context, operation):
        return _foral_projection(resolver_id)
    observations = _m100_claim_observations(history.claims, period=period)
    reached = {observation.target_casilla_id for observation in observations}
    forecast = _Forecast(context, operation)
    diagnostics = tuple(
        diagnostic
        for asset_id in sorted(current)
        for diagnostic in _m100_gap_diagnostics(
            current[asset_id],
            history,
            tax_year=period.filing_year,
            reached=reached,
            forecast=forecast,
            resolver_id=resolver_id,
        )
    )
    return ActivityAssetProjection(observations=observations, diagnostics=diagnostics)


def m130_activity_asset_projection(
    history: ActivityAssetHistory,
    *,
    context: CalculationSourceContext,
    period: Period,
    target_casilla_id: CasillaId,
    transactions: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    resolver_id: str,
) -> ActivityAssetProjection:
    """Project each element's amortization accrued from 1 January to the quarter's end.

    An element belongs to the activity its acquisition row declares. An agrarian
    activity pays a share of income whatever its expenses, so its elements stay
    out; the filter is by activity, and another element of the same taxpayer still
    counts. An element whose row declares no activity counts, because silence does
    not mean agrarian.

    Returns:
        The accrued observations and the findings about elements that contributed nothing.
    """
    current = current_revisions(history.revisions)
    if not current:
        return ActivityAssetProjection()
    if _foral(context, operation):
        return _foral_projection(resolver_id)
    agrarian = frozenset(
        TipoActividad(code)
        for code in tipo_actividad_code_set(
            _AGRARIAN_INSTALMENT_SELECTOR,
            effective_date=period.end_date,
            authority=operation,
        )
    )
    rows = transactions.load_by_ids(
        revision.acquisition.observed_transaction_id for revision in current.values()
    ).transactions
    activities = {
        asset_id: (row.tipo_actividad if (row := rows.get(revision.acquisition.observed_transaction_id)) else None)
        for asset_id, revision in current.items()
    }
    observations: list[ActivityAssetExpenseObservation] = []
    diagnostics: list[CalculationSourceDiagnostic] = []
    for accrual in m130_register_accruals(
        history,
        forecast=_Forecast(context, operation),
        period_end=period.end_date,
        activities=activities,
        agrarian=agrarian,
    ):
        if accrual.activity_undeclared:
            diagnostics.append(_activity_undeclared_diagnostic(accrual.revision, resolver_id=resolver_id))
        observations.extend(
            ActivityAssetExpenseObservation(
                source=(
                    ActivityAssetClaimSource(claim_id=item.claim_id)
                    if item.claim_id is not None
                    else ActivityAssetScheduleSource(schedule_fingerprint=item.schedule_fingerprint or "")
                ),
                modelo="130",
                period=period.registry_token,
                target_casilla_id=target_casilla_id,
                deductible_amount=item.amount,
            )
            for item in accrual.contributions
        )
        diagnostics.extend(
            _m130_accrual_diagnostics(
                accrual, period=period, target_casilla_id=target_casilla_id, resolver_id=resolver_id
            )
        )
    return ActivityAssetProjection(observations=tuple(observations), diagnostics=tuple(diagnostics))


def _m130_accrual_diagnostics(
    accrual: M130ElementAccrual,
    *,
    period: Period,
    target_casilla_id: CasillaId,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    revision = accrual.revision
    if accrual.outcome is M130ElementOutcome.AGRARIAN_EXCLUDED:
        return (_agrarian_excluded_diagnostic(revision, period=period, resolver_id=resolver_id),)
    if accrual.outcome is M130ElementOutcome.UNAVAILABLE and accrual.error is not None:
        return (_accrual_unavailable_diagnostic(revision, accrual.error, casilla_id=None, resolver_id=resolver_id),)
    if accrual.outcome is not M130ElementOutcome.FREE_GAP:
        return ()
    start = max(date(period.filing_year, 1, 1), revision.in_service_date)
    return (
        CalculationSourceDiagnostic(
            reason="activity_asset_claim_gap",
            source_kind=resolver_id,
            resolver_id=resolver_id,
            source_ref=f"activity-asset:{revision.asset_id}",
            message=(
                f"element {revision.asset_id!r} has no effective claim for {start.isoformat()} to "
                f"{period.end_date.isoformat()} and no computable accrual, because the amount of a free method "
                f"is the taxpayer's election; it contributes nothing to box {target_casilla_id}"
            ),
            remedy="record the elected amortization charge to deduct it",
        ),
    )


def activity_asset_provenance(
    observations: Iterable[ActivityAssetExpenseObservation],
    *,
    resolver_id: str,
    resolved_binding_source: BindingSourceKind,
) -> tuple[CalculationSourceProvenance, ...]:
    """Name the claim or schedule behind each observation.

    Returns:
        One primary provenance row per observation.
    """
    return tuple(
        CalculationSourceProvenance(
            resolver_id=resolver_id,
            resolved_binding_source=resolved_binding_source,
            contributor_source_kind=observation.source.contributor_source_kind,
            contributor_binding_source=None,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=observation.source.source_ref,
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        )
        for observation in observations
    )


def _foral(context: CalculationSourceContext, operation: PinnedAuthorityOperation) -> bool:
    profile = context.profile
    return (
        resident_territory(
            bucket_id=context.bucket_id,
            profile_record=None if profile is None else profile.record,
            profile_decode_context=None if profile is None else profile.profile_decode_context,
            operation=operation,
        )
        is ResidenceTerritory.FORAL
    )


def _foral_projection(resolver_id: str) -> ActivityAssetProjection:
    return ActivityAssetProjection(
        diagnostics=(
            CalculationSourceDiagnostic(
                reason="activity_asset_foral_territory",
                source_kind=resolver_id,
                resolver_id=resolver_id,
                message=(
                    "the taxpayer resides in a foral territory, where Modelos 100 and 130 of the AEAT do not apply; "
                    "the activity-asset register contributes nothing to this calculation"
                ),
                remedy="declare these assets with the foral Hacienda of your territory",
            ),
        ),
    )


def _m100_claim_observations(
    claims: tuple[AmortizationClaim, ...],
    *,
    period: Period,
) -> tuple[ActivityAssetExpenseObservation, ...]:
    return tuple(
        ActivityAssetExpenseObservation(
            source=ActivityAssetClaimSource(claim_id=claim.claim_id),
            modelo="100",
            period=period.registry_token,
            target_casilla_id=validated_casilla_id(
                m100_casilla_id(claim.asset_kind),
                surface="activity asset M100 observation",
            ),
            deductible_amount=claim.amount,
        )
        for claim in select_effective_claims(claims, tax_year=period.filing_year)
    )


def _year_history(
    history: ActivityAssetHistory,
    revision: ActivityAssetRevision,
    *,
    tax_year: int,
) -> AssetScheduleHistory:
    """Summarise history up to ``tax_year``: a later year's claim does not change this year's figure."""
    return asset_schedule_history(
        tuple(claim for claim in history.claims if claim.tax_year <= tax_year),
        history.revisions,
        asset_id=revision.asset_id,
        tax_year=tax_year,
    )


def _m100_gap_diagnostics(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    tax_year: int,
    reached: set[CasillaId],
    forecast: _Forecast,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    casilla = validated_casilla_id(m100_casilla_id(revision.asset_kind), surface="activity asset M100 finding")
    named_box = None if casilla in reached else casilla
    diagnostics: list[CalculationSourceDiagnostic] = []
    for gap in uncovered_claim_intervals(
        revision,
        history.claims,
        start=date(tax_year, 1, 1),
        end=date(tax_year + 1, 1, 1),
    ):
        if revision.amortization.method in FREE_AMOUNT_METHODS:
            if not free_base_remains(revision, history, tax_year=tax_year):
                continue
            accrued = "no computable accrual, because the amount of a free method is the taxpayer's election"
        else:
            try:
                charge = forecast(
                    revision,
                    covered_from=gap.covered_from,
                    covered_until=gap.covered_until,
                    history=_year_history(history, revision, tax_year=tax_year),
                )
            except ActividadAssetPeriodElapsedError:
                continue
            except ActividadAssetError as exc:
                diagnostics.append(
                    _accrual_unavailable_diagnostic(revision, exc, casilla_id=named_box, resolver_id=resolver_id),
                )
                continue
            if charge.amount <= Decimal("0"):
                continue
            accrued = f"{charge.amount} EUR accrued"
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="activity_asset_claim_gap",
                source_kind=resolver_id,
                resolver_id=resolver_id,
                source_ref=f"activity-asset:{revision.asset_id}",
                casilla_id=named_box,
                message=(
                    f"element {revision.asset_id!r} has no effective claim for "
                    f"{gap.covered_from.isoformat()} to {gap.covered_until.isoformat()} ({accrued}); "
                    f"box {casilla} declares only recorded claims"
                ),
                remedy="record the amortization charge for that interval to deduct it",
            ),
        )
    return tuple(diagnostics)


def _accrual_unavailable_diagnostic(
    revision: ActivityAssetRevision,
    error: ActividadAssetError | RegistryError,
    *,
    casilla_id: CasillaId | None,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="activity_asset_accrual_unavailable",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        casilla_id=casilla_id,
        message=f"the schedule of element {revision.asset_id!r} could not be worked out: {error}",
        remedy="complete or correct the element in the register, then calculate again",
    )


def _agrarian_excluded_diagnostic(
    revision: ActivityAssetRevision,
    *,
    period: Period,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="activity_asset_agrarian_excluded",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        message=(
            f"element {revision.asset_id!r} belongs to an agrarian activity, whose {period.registry_token} instalment "
            "is a share of income (RIRPF art. 110.1.c); its amortization is deducted in Modelo 100 only"
        ),
    )


def _activity_undeclared_diagnostic(
    revision: ActivityAssetRevision,
    *,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="activity_asset_activity_undeclared",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"transaction:{revision.acquisition.observed_transaction_id}",
        message=(
            f"the acquisition of element {revision.asset_id!r} declares no activity, and another element of this "
            "taxpayer is agrarian; it is counted as non-agrarian"
        ),
        remedy="set the type of activity on the acquisition entry, then calculate again",
    )


def amortization_labelled_expense_categories(*, effective_date: date) -> frozenset[str]:
    """Return the ledger categories that declare an amortization rather than an ordinary expense.

    The governed spending-category catalogue selected at ``effective_date`` names
    them. They have no first-slice route, so the catalogue is the only place that
    keeps their rows from being read as ordinary expenses.

    Returns:
        The category tokens whose rows belong to the activity-asset register.
    """
    return frozenset(category.value for category in amortizable_spending_categories(effective_date=effective_date))


class UnregisteredAmortizationRow(BaseModel):
    """A ledger row declaring an amortization that no registered element accounts for."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int


@dataclass(frozen=True, slots=True)
class LedgerExpenseRegisterClassification:
    """Which ledger rows the register withholds, and which it refuses to leave unexplained."""

    withheld: tuple[RegisterOwnedAcquisition, ...]
    unregistered: tuple[UnregisteredAmortizationRow, ...]

    @property
    def excluded_transaction_ids(self) -> frozenset[str]:
        """Return the rows that must not reach an expense total."""
        return frozenset(
            {row.transaction_id for row in self.withheld} | {row.transaction_id for row in self.unregistered},
        )


def classify_ledger_expenses_against_asset_register(
    assets: tuple[ActivityAssetRevision, ...],
    treatments: tuple[LedgerRentaExpenseTreatment, ...],
) -> LedgerExpenseRegisterClassification:
    """Withhold register-owned acquisitions and report unowned amortization rows.

    The activity-asset source owns the activity amortization destinations
    exclusively, in every year and whether or not it holds a claim for that year,
    so no ledger row may route a deductible amount to one:

    - A row on a transaction a registered asset declares as its acquisition IS
      the acquisition. Under LIRPF art. 28.1 the rendimiento neto follows the
      Impuesto sobre Sociedades rules, where LIS art. 12.1 makes the deductible
      item the amortización del inmovilizado and RIS art. 3.2 makes the
      acquisition price the amortizable base, amortised across the element's
      useful life (RIS art. 3.3). The row is withheld and reported, whatever
      category it carries; the transaction and its IVA facts are untouched.
    - Any other row whose own destination is an activity amortization casilla is
      an element the register does not know. It is never deducted, and the
      caller turns it into a blocking note whose remedy is to register the element.

    Returns:
        The withheld rows in asset order and the unregistered rows in ledger order.
    """
    owners = _current_acquisition_owners(assets)
    owned = {transaction_id for _asset_id, transaction_id in owners}
    return LedgerExpenseRegisterClassification(
        withheld=tuple(
            RegisterOwnedAcquisition(
                asset_id=asset_id,
                transaction_id=treatment.transaction_id,
                category=treatment.category,
                tax_year=treatment.tax_year,
                purchase_amount=treatment.deductible_amount,
            )
            for asset_id, transaction_id in owners
            for treatment in treatments
            if treatment.transaction_id == transaction_id
        ),
        unregistered=tuple(
            UnregisteredAmortizationRow(
                transaction_id=treatment.transaction_id,
                category=treatment.category,
                tax_year=treatment.tax_year,
            )
            for treatment in treatments
            if treatment.amortization_labelled and treatment.transaction_id not in owned
        ),
    )


class RefusedExpenseRow(Protocol):
    """What an aggregation issue says about the ledger row it refused."""

    @property
    def transaction_id(self) -> str:
        """The refused ledger row."""
        ...

    @property
    def category_id(self) -> str | None:
        """The category the row declares."""
        ...

    @property
    def reason(self) -> str:
        """The machine-readable refusal."""
        ...


def refused_amortization_rows(
    issues: Iterable[RefusedExpenseRow],
    *,
    assets: tuple[ActivityAssetRevision, ...],
    tax_year: int,
    effective_date: date,
) -> tuple[UnregisteredAmortizationRow, ...]:
    """Find amortization rows the expense rules refused, which never became observations.

    A row in an amortizable category has no route and no deduction of its own, so
    it is refused before it can be classified. Such a row still declares an
    element the register does not know, so an advisory alone would omit it.

    Returns:
        One row per refused, unowned, amortization-labelled expense of this period.
    """
    declared = tuple(
        issue
        for issue in issues
        if issue.category_id is not None and str(issue.reason) not in _NOT_A_DECLARED_EXPENSE_ISSUE_REASONS
    )
    if not declared:
        return ()
    labelled = amortization_labelled_expense_categories(effective_date=effective_date)
    owned = register_acquisition_transaction_ids(assets)
    return tuple(
        UnregisteredAmortizationRow(
            transaction_id=issue.transaction_id,
            category=issue.category_id,
            tax_year=tax_year,
        )
        for issue in declared
        if issue.category_id in labelled and issue.transaction_id not in owned
    )


def refused_register_owned_rows(
    issues: Iterable[RefusedExpenseRow],
    *,
    assets: tuple[ActivityAssetRevision, ...],
    tax_year: int,
    effective_date: date,
) -> tuple[RegisterOwnedAcquisition, ...]:
    """Find acquisitions the register owns that the expense rules refused outright.

    A row in an amortizable category deducts nothing, so it never becomes an
    observation to withhold. The register still owns it, and the operator is told
    so, without a purchase amount that no observation carries.

    Returns:
        One withheld acquisition per refused, owned, amortization-labelled expense of this period.
    """
    declared = tuple(
        issue
        for issue in issues
        if issue.category_id is not None and str(issue.reason) not in _NOT_A_DECLARED_EXPENSE_ISSUE_REASONS
    )
    if not declared:
        return ()
    labelled = amortization_labelled_expense_categories(effective_date=effective_date)
    owners = {transaction_id: asset_id for asset_id, transaction_id in _current_acquisition_owners(assets)}
    return tuple(
        RegisterOwnedAcquisition(
            asset_id=owners[issue.transaction_id],
            transaction_id=issue.transaction_id,
            category=issue.category_id,
            tax_year=tax_year,
        )
        for issue in declared
        if issue.category_id in labelled and issue.transaction_id in owners
    )


def unregistered_amortization_row_diagnostics(
    rows: Iterable[UnregisteredAmortizationRow],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project each unowned amortization row into its blocking note.

    Returns:
        One note per row, naming the row and the remedy.
    """
    return source_diagnostics_for(
        tuple({row.transaction_id: row for row in rows}.values()),
        reason="ledger_amortization_row_unregistered",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=lambda row: f"transaction:{row.transaction_id}",
        message=lambda row: (
            f"ledger transaction {row.transaction_id!r} (category={row.category!r}, tax_year={row.tax_year}) declares "
            "an amortizable element the activity-asset register does not hold; it deducts nothing"
        ),
        remedy=lambda _row: (
            "register the element in the activity-asset register, naming this transaction as its acquisition, "
            "or reclassify the row if it is not an amortizable element"
        ),
    )


def register_owned_acquisition_diagnostics(
    withheld: tuple[RegisterOwnedAcquisition, ...],
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project each withheld acquisition into an operator-visible advisory.

    Returns:
        One advisory per withheld row, naming the asset, the transaction, and the
        purchase amount that did not enter the expense total.
    """
    return source_diagnostics_for(
        withheld,
        reason="register_owned_capital_acquisition",
        source_kind=source_kind,
        resolver_id=resolver_id,
        source_ref=lambda acquisition: f"transaction:{acquisition.transaction_id}",
        message=lambda acquisition: (
            f"ledger transaction {acquisition.transaction_id!r} is the activity-asset register's declared "
            f"acquisition of asset {acquisition.asset_id!r} (category={acquisition.category!r}, "
            f"tax_year={acquisition.tax_year}); its "
            + (
                "purchase amount"
                if acquisition.purchase_amount is None
                else f"{acquisition.purchase_amount} EUR purchase amount"
            )
            + " is the amortizable base, not a deductible expense of the period, so it is not declared in this "
            "expense total"
        ),
        remedy=lambda _acquisition: (
            "the register owns this asset's Renta deduction: record the year's amortization charge so the "
            "schedule's claim is declared instead of the purchase"
        ),
    )


def _current_acquisition_owners(
    assets: tuple[ActivityAssetRevision, ...],
) -> tuple[tuple[str, str], ...]:
    """Return ``(asset_id, acquisition transaction id)`` for each asset's current revision.

    A superseding revision may restate the acquisition linkage, so only the
    highest revision number of each asset declares which transaction the
    register owns. Pairs are returned rather than a mapping so two assets that
    name the same transaction both keep their disposition instead of one
    silently displacing the other.
    """
    current = current_revisions(assets)
    return tuple((asset_id, current[asset_id].acquisition.observed_transaction_id) for asset_id in sorted(current))


def register_acquisition_transaction_ids(assets: tuple[ActivityAssetRevision, ...]) -> frozenset[str]:
    """Return the ledger transactions the register declares as an asset's acquisition.

    Returns:
        The acquisition transaction id of every asset's current revision.
    """
    return frozenset(transaction_id for _asset_id, transaction_id in _current_acquisition_owners(assets))


def dwelling_ownership_share(assets: tuple[ActivityAssetRevision, ...]) -> Decimal | None:
    """Return the taxpayer's ownership share of the partly affected property the register records.

    A mixed-use property is registered with a whole-property basis, which states
    the taxpayer's direct ownership share of it. That share is the only source
    of the ownership fact the dwelling's own expenses need.

    Returns:
        The share when every registered whole-property asset states the same
        one, or ``None`` when no such asset exists or two state different
        shares, since the ledger rows do not say which property they belong to.
    """
    shares = {
        revision.basis.ownership_share
        for revision in current_revisions(assets).values()
        if revision.basis.stage is AssetBasisStage.WHOLE_PROPERTY and revision.basis.ownership_share is not None
    }
    return next(iter(shares)) if len(shares) == 1 else None


__all__ = [
    "ActivityAssetClaimSource",
    "ActivityAssetExpenseObservation",
    "ActivityAssetProjection",
    "ActivityAssetScheduleSource",
    "LedgerExpenseRegisterClassification",
    "LedgerRentaExpenseTreatment",
    "RefusedExpenseRow",
    "RegisterOwnedAcquisition",
    "UnregisteredAmortizationRow",
    "activity_asset_provenance",
    "amortization_labelled_expense_categories",
    "classify_ledger_expenses_against_asset_register",
    "dwelling_ownership_share",
    "m100_activity_asset_projection",
    "m130_activity_asset_projection",
    "refused_amortization_rows",
    "refused_register_owned_rows",
    "register_acquisition_transaction_ids",
    "register_owned_acquisition_diagnostics",
    "unregistered_amortization_row_diagnostics",
]
