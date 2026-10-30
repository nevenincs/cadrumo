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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Protocol

from pydantic import BaseModel, Field

from ...core.aggregation import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    LedgerIncomeGrounding,
    LedgerWithholdingDerivation,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.actividad_asset_disposal_bindings import (
    ELEMENT_ROW_ROUTES,
    ActivityAssetDisposalRoute,
    activity_asset_disposal_route_casillas,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.irpf_regimes import irpf_estimation_regime_objetiva_token
from ...domain.categories.spending_category_catalogue import amortizable_spending_categories
from ...domain.contribuyente.tax_residence import ResidenceTerritory
from ...domain.modelos.calculation_revision_sources import (
    ACTIVITY_ASSET_CLAIM_REF_PREFIX,
    ACTIVITY_ASSET_DISPOSAL_REF_PREFIX,
    ACTIVITY_ASSET_SCHEDULE_REF_PREFIX,
)
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    asset_schedule_history,
    claims_through_year,
    current_revisions,
    m100_casilla_id,
    select_effective_claims,
    uncovered_claim_intervals,
)
from ...domain.renta.actividad_asset.disposal import (
    BAJA_WITHOUT_TRANSMISSION_REASONS,
    TRANSMISSION_REASONS,
    ActivityAssetDisposalCalculation,
    ActivityAssetDisposalReason,
)
from ...domain.renta.actividad_asset.election import FREE_AMOUNT_METHODS
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetError,
    ActividadAssetPeriodElapsedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetBasisStage
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ..actividad_asset.disposal_calculation import (
    calculate_element_disposal,
    disposal_excess_applies,
    pinned_disposal_bounds,
)
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.schedule_walk import (
    M130ElementAccrual,
    M130ElementOutcome,
    free_base_remains,
    m130_register_accruals,
)
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..invoices.catalogue_reads_ports import TransactionCatalogueReader
from ..user_profile.plantilla_media_rows import plantilla_media_years_of
from ..user_profile.projections import record_to_path_values
from . import _shared_issue_reasons
from .renta_ledger import resident_territory
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceProvenance
from .source_resolution_operations import source_diagnostics_for

_AGRARIAN_INSTALMENT_SELECTOR: Final[str] = (
    "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras"
)
"""The activities whose instalment is a share of income under RIRPF art. 110.1.c."""

_NOT_THIS_RETURN: Final[frozenset[ResidenceTerritory]] = frozenset(
    {ResidenceTerritory.FORAL, ResidenceTerritory.UNRESOLVED},
)
"""The readings under which the register contributes nothing to a calculation."""

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
class ActivityAssetDisposalObservation:
    """One figure of a baja on its way to the box the revision gives its route."""

    revision_id: str
    route: ActivityAssetDisposalRoute
    amount: Decimal


@dataclass(frozen=True, slots=True)
class ActivityAssetProjection:
    """What the register contributes to one calculation, and what it has to say about it."""

    observations: tuple[ActivityAssetExpenseObservation, ...] = ()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    disposal_revision_ids: tuple[str, ...] = ()
    disposal_observations: tuple[ActivityAssetDisposalObservation, ...] = ()


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
    transactions: TransactionCatalogueReader,
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
    territory = _territory(context, operation, as_of=period.end_date)
    if (outside := _outside_this_calculation(territory, resolver_id)) is not None:
        return outside
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
    disposed = tuple(
        current[asset_id]
        for asset_id in sorted(current)
        if (baja := current[asset_id].disposal) is not None and baja.disposal_date.year == period.filing_year
    )
    reader = _BajaReader(context, operation, period=period, transactions=transactions, resolver_id=resolver_id)
    bajas = tuple(reader.read(revision, history) for revision in disposed)
    return ActivityAssetProjection(
        observations=observations,
        diagnostics=(
            *_residence_period_findings(territory, period=period, resolver_id=resolver_id),
            *diagnostics,
            *(note for baja in bajas for note in baja.notes),
        ),
        disposal_revision_ids=tuple(revision.revision_id for revision in disposed),
        disposal_observations=tuple(item for baja in bajas for item in baja.observations),
    )


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

    An element belongs to the activity it or its acquisition row declares. An agrarian
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
    territory = _territory(context, operation, as_of=period.end_date)
    if (outside := _outside_this_calculation(territory, resolver_id)) is not None:
        return outside
    agrarian = frozenset(
        TipoActividad(code)
        for code in tipo_actividad_code_set(
            _AGRARIAN_INSTALMENT_SELECTOR,
            effective_date=period.end_date,
            authority=operation,
        )
    )
    rows = transactions.load_by_ids(
        transaction_id for revision in current.values() for transaction_id in revision.acquisition_transaction_ids
    ).transactions
    activities = {asset_id: revision.activity_in(rows) for asset_id, revision in current.items()}
    observations: list[ActivityAssetExpenseObservation] = []
    diagnostics = list(_residence_period_findings(territory, period=period, resolver_id=resolver_id))
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
    disposed = _bajas_reached(history, period=period)
    for row in _m130_excess_rows(disposed, history, operation=operation, agrarian=agrarian, rows=rows):
        diagnostics.extend(_m130_excess_notes(row, resolver_id=resolver_id))
    return ActivityAssetProjection(
        observations=tuple(observations),
        diagnostics=tuple(diagnostics),
        disposal_revision_ids=tuple(revision.revision_id for revision in disposed),
    )


@dataclass(frozen=True, slots=True)
class ActivityAssetDisposalExcess:
    """What a baja the period reaches says about income: an excess, or why it cannot say."""

    revision: ActivityAssetRevision
    amount: Decimal = Decimal("0.00")
    agrarian: bool = False
    error: ActividadAssetError | RegistryError | None = None

    @property
    def source_ref(self) -> str:
        """Identify the excess in the income resolver's provenance."""
        return f"activity-asset-disposal-excess:{self.revision.revision_id}"

    @property
    def transaction_id(self) -> str:
        """Name the income row by its baja; an excess has no ledger row of its own."""
        return self.source_ref

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the instalment casilla the instructions give the excess."""
        return validated_casilla_id("01")

    @property
    def gross_amount(self) -> Decimal:
        """Return the excess as income."""
        return self.amount

    @property
    def taxable_base_amount(self) -> Decimal:
        """Return the excess, which carries no IVA."""
        return self.amount

    @property
    def withheld_amount(self) -> Decimal:
        """Return zero: nothing is withheld on an excess."""
        return Decimal("0")

    @property
    def withheld_derivation(self) -> LedgerWithholdingDerivation:
        """Say that nothing was withheld."""
        return LedgerWithholdingDerivation.NONE_WITHHELD

    @property
    def grounding(self) -> LedgerIncomeGrounding:
        """Say the figure rests on a declared base rather than on bank cash."""
        return LedgerIncomeGrounding.SUBSTRATE_DECLARED


def _bajas_reached(history: ActivityAssetHistory, *, period: Period) -> tuple[ActivityAssetRevision, ...]:
    """Return the current revisions whose baja falls in the period's year, on or before its end."""
    current = current_revisions(history.revisions)
    return tuple(
        current[asset_id]
        for asset_id in sorted(current)
        if (baja := current[asset_id].disposal) is not None
        and baja.disposal_date.year == period.filing_year
        and baja.disposal_date <= period.end_date
    )


def _m130_excess_rows(
    disposed: tuple[ActivityAssetRevision, ...],
    history: ActivityAssetHistory,
    *,
    operation: PinnedAuthorityOperation,
    agrarian: frozenset[TipoActividad],
    rows: Mapping[str, Transaction],
) -> tuple[ActivityAssetDisposalExcess, ...]:
    found: list[ActivityAssetDisposalExcess] = []
    for revision in disposed:
        is_agrarian = revision.activity_in(rows) in agrarian
        disposal = revision.disposal
        if disposal is None or not disposal_excess_applies(revision, disposal):
            continue
        try:
            amount = _calculate(revision, history, operation=operation).excess
        except (ActividadAssetError, RegistryError) as error:
            found.append(ActivityAssetDisposalExcess(revision=revision, agrarian=is_agrarian, error=error))
            continue
        if amount > Decimal("0"):
            found.append(ActivityAssetDisposalExcess(revision=revision, amount=amount, agrarian=is_agrarian))
    return tuple(found)


def activity_asset_disposal_excess(
    history: ActivityAssetHistory,
    *,
    context: CalculationSourceContext,
    period: Period,
    transactions: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ActivityAssetDisposalExcess, ...]:
    """Return the excess each baja the period reaches contributes to income.

    It belongs to the quarter of the transmission and stays in the later
    cumulative quarters (LIRPF DA 59.2 and the casilla 01 instruction).

    Returns:
        One row per baja with an excess or a calculation that failed; a foral
        resident has none, because no such return applies.
    """
    disposed = _bajas_reached(history, period=period)
    if not disposed or _territory(context, operation, as_of=period.end_date) in _NOT_THIS_RETURN:
        return ()
    agrarian = frozenset(
        TipoActividad(code)
        for code in tipo_actividad_code_set(
            _AGRARIAN_INSTALMENT_SELECTOR,
            effective_date=period.end_date,
            authority=operation,
        )
    )
    rows = transactions.load_by_ids(
        transaction_id for revision in disposed for transaction_id in revision.acquisition_transaction_ids
    ).transactions
    return _m130_excess_rows(disposed, history, operation=operation, agrarian=agrarian, rows=rows)


def _calculate(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetDisposalCalculation:
    disposal = revision.disposal
    if disposal is None:  # defensive: callers select revisions with a baja
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.disposal_not_recorded")
    return calculate_element_disposal(revision, disposal, history, bounds=pinned_disposal_bounds(operation))


def _disposal_finding(
    revision: ActivityAssetRevision, message: str, *, resolver_id: str
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="activity_asset_disposal_finding",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        message=f"baja of element {revision.asset_id!r}: {message}",
    )


def _m100_unresolved_disposal(
    revision: ActivityAssetRevision,
    error: ActividadAssetError | RegistryError,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Leave a baja's figures unresolved and say so; incomplete history never stops the return.

    A withdrawal computes no gain, so it has nothing to say.  A possible excess is
    activity income the filer has to account for, so the finding says that too.
    """
    disposal = revision.disposal
    if disposal is None or disposal.reason is ActivityAssetDisposalReason.WITHDRAWAL:
        return ()
    message = f"its result could not be worked out ({error})"
    if disposal_excess_applies(revision, disposal):
        return (
            _disposal_finding(revision, f"{message}, so activity income may be understated", resolver_id=resolver_id),
        )
    return (_disposal_finding(revision, f"{message}; no box carries it", resolver_id=resolver_id),)


def _m130_excess_notes(
    row: ActivityAssetDisposalExcess,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if row.error is not None:
        return (
            _disposal_finding(
                row.revision,
                f"its excess could not be worked out ({row.error}), so this instalment carries none",
                resolver_id=resolver_id,
            ),
        )
    if row.agrarian:
        return (
            _disposal_finding(
                row.revision,
                f"{row.amount} EUR of excess in an agrarian activity has no established instalment line; "
                "it is left to you",
                resolver_id=resolver_id,
            ),
        )
    return ()


def activity_asset_disposal_excess_m131_findings(
    excess: tuple[ActivityAssetDisposalExcess, ...],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Say that an excess reaches no Modelo 131 line, whose instructions are silent on it.

    Returns:
        One non-blocking finding per excess.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="activity_asset_disposal_finding",
            source_kind=resolver_id,
            resolver_id=resolver_id,
            source_ref=f"activity-asset:{row.revision.asset_id}",
            message=(
                f"{row.amount} EUR of excess from the baja of element {row.revision.asset_id!r} is not routed to "
                "Modelo 131, whose instructions do not address it"
            ),
        )
        for row in excess
        if row.error is None
    )


@dataclass(frozen=True, slots=True)
class _BajaReading:
    observations: tuple[ActivityAssetDisposalObservation, ...] = ()
    notes: tuple[CalculationSourceDiagnostic, ...] = ()


class _BajaReader:
    """Read each baja of one Modelo 100 calculation into the boxes its revision binds.

    A gain or loss never reaches casilla 02 or the rendimiento neto.  A figure the
    edition does not bind, or whose line is not established, stays in front of the
    filer as a finding.
    """

    def __init__(
        self,
        context: CalculationSourceContext,
        operation: PinnedAuthorityOperation,
        *,
        period: Period,
        transactions: TransactionCatalogueReader,
        resolver_id: str,
    ) -> None:
        self._context = context
        self._operation = operation
        self._period = period
        self._transactions = transactions
        self._resolver_id = resolver_id
        self._routes = activity_asset_disposal_route_casillas(context.revision)

    def read(self, revision: ActivityAssetRevision, history: ActivityAssetHistory) -> _BajaReading:
        try:
            calculation = _calculate(revision, history, operation=self._operation)
        except (ActividadAssetError, RegistryError) as error:
            return _BajaReading(notes=_m100_unresolved_disposal(revision, error, resolver_id=self._resolver_id))
        figures: list[tuple[ActivityAssetDisposalRoute, Decimal]] = []
        notes: list[CalculationSourceDiagnostic] = []
        if calculation.route_changed_by_later_affectation:
            notes.append(self._finding(revision, _later_affectation_message(calculation)))
        elif (route := _result_route(revision, calculation)) is not None and calculation.result is not None:
            figures.append((route, abs(calculation.result)))
        if calculation.excess > Decimal("0"):
            excess_route = self._excess_route(revision)
            if excess_route is None:
                notes.append(
                    self._finding(
                        revision,
                        f"{calculation.excess} EUR of excess in an agrarian activity under modulos has no established "
                        "line; it is left to you",
                    ),
                )
            else:
                figures.append((excess_route, calculation.excess))
        notes.extend(self._figure_finding(revision, route, amount) for route, amount in figures)
        notes.extend(
            self._finding(
                revision,
                finding.kind.value
                + ("" if finding.tax_year is None else f" in {finding.tax_year}")
                + (
                    "" if finding.effect_on_cost is None else f", raising the reduction by {finding.effect_on_cost} EUR"
                ),
            )
            for finding in calculation.findings
        )
        return _BajaReading(
            observations=tuple(
                ActivityAssetDisposalObservation(revision_id=revision.revision_id, route=route, amount=amount)
                for route, amount in figures
                if route in self._routes
            ),
            notes=tuple(notes),
        )

    def _finding(self, revision: ActivityAssetRevision, message: str) -> CalculationSourceDiagnostic:
        return _disposal_finding(revision, message, resolver_id=self._resolver_id)

    def _figure_finding(
        self,
        revision: ActivityAssetRevision,
        route: ActivityAssetDisposalRoute,
        amount: Decimal,
    ) -> CalculationSourceDiagnostic:
        box = self._routes.get(route)
        if box is None:
            return self._finding(revision, f"{amount} EUR ({route.value}) reaches no box of this edition")
        return self._finding(revision, f"{amount} EUR ({route.value}) enters box {box}{self._row_entry(route)}")

    def _row_entry(self, route: ActivityAssetDisposalRoute) -> str:
        if route in ELEMENT_ROW_ROUTES:
            return "; on its row, enter the dates and values"
        if route in _PROPERTY_ROW_ROUTES:
            return "; on its row, mark the property as affected to an activity and enter the dates and values"
        return ""

    def _excess_route(self, revision: ActivityAssetRevision) -> ActivityAssetDisposalRoute | None:
        """Follow the determination method of the disposal year: an agrarian one under modulos has no line."""
        profile = self._context.profile
        token = (
            None
            if profile is None
            else record_to_path_values(profile.record, as_of=self._period.end_date).get(_ESTIMATION_REGIME_PATH)
        )
        if token != str(irpf_estimation_regime_objetiva_token(authority=self._operation)):
            return ActivityAssetDisposalRoute.EXCESS_DIRECT_ESTIMATION
        activity = revision.activity_in(self._transactions.load().transactions)
        agrarian = frozenset(
            TipoActividad(code)
            for code in tipo_actividad_code_set(
                _AGRARIAN_INSTALMENT_SELECTOR,
                effective_date=self._period.end_date,
                authority=self._operation,
            )
        )
        if activity in agrarian:
            return None
        return ActivityAssetDisposalRoute.EXCESS_OBJECTIVE_ESTIMATION


_ESTIMATION_REGIME_PATH: Final[str] = "irpf.estimation_regime"
_PROPERTY_ROW_ROUTES: Final[frozenset[ActivityAssetDisposalRoute]] = frozenset(
    {ActivityAssetDisposalRoute.TRANSMISSION_GAIN_PROPERTY, ActivityAssetDisposalRoute.TRANSMISSION_LOSS_PROPERTY},
)


def _later_affectation_message(calculation: ActivityAssetDisposalCalculation) -> str:
    return (
        f"the sale falls within the period after a later affectation that changes its route (LIRPF art. 28.3), so its "
        f"result of {calculation.result} EUR enters no box and is left to you"
    )


def _result_route(
    revision: ActivityAssetRevision,
    calculation: ActivityAssetDisposalCalculation,
) -> ActivityAssetDisposalRoute | None:
    disposal = revision.disposal
    result = calculation.result
    if disposal is None or result is None or result == Decimal("0"):
        return None
    gain = result > Decimal("0")
    if disposal.reason in BAJA_WITHOUT_TRANSMISSION_REASONS:
        return (
            ActivityAssetDisposalRoute.NO_TRANSMISSION_GAIN if gain else ActivityAssetDisposalRoute.NO_TRANSMISSION_LOSS
        )
    if disposal.reason not in TRANSMISSION_REASONS:
        return None
    if revision.basis.is_property:
        return (
            ActivityAssetDisposalRoute.TRANSMISSION_GAIN_PROPERTY
            if gain
            else ActivityAssetDisposalRoute.TRANSMISSION_LOSS_PROPERTY
        )
    return (
        ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT
        if gain
        else ActivityAssetDisposalRoute.TRANSMISSION_LOSS_ELEMENT
    )


def activity_asset_disposal_provenance(
    disposal_revision_ids: Iterable[str],
    *,
    resolver_id: str,
    resolved_binding_source: BindingSourceKind,
) -> tuple[CalculationSourceProvenance, ...]:
    """Name each baja a calculation's period reaches, which the drift gate compares.

    Returns:
        One primary provenance row per baja.
    """
    return tuple(
        CalculationSourceProvenance(
            resolver_id=resolver_id,
            resolved_binding_source=resolved_binding_source,
            contributor_source_kind=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL.value,
            contributor_binding_source=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=f"{ACTIVITY_ASSET_DISPOSAL_REF_PREFIX}{revision_id}",
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        )
        for revision_id in disposal_revision_ids
    )


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


def _territory(
    context: CalculationSourceContext,
    operation: PinnedAuthorityOperation,
    *,
    as_of: date,
) -> ResidenceTerritory:
    profile = context.profile
    return resident_territory(
        bucket_id=context.bucket_id,
        profile_record=None if profile is None else profile.record,
        profile_decode_context=None if profile is None else profile.profile_decode_context,
        operation=operation,
        as_of=as_of,
    )


def _residence_period_findings(
    territory: ResidenceTerritory,
    *,
    period: Period,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Say that no recorded residence covers this period; the register counts, as nothing places it elsewhere."""
    if territory is not ResidenceTerritory.PERIOD_UNKNOWN:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="activity_asset_residence_period_unknown",
            source_kind=resolver_id,
            resolver_id=resolver_id,
            message=(
                f"no recorded tax residence is in force on {period.end_date.isoformat()}; the activity-asset register "
                "is counted as if Modelos 100 and 130 of the AEAT apply to this period"
            ),
            remedy="state the tax residence that applied in this period in the profile",
        ),
    )


def _outside_this_calculation(
    territory: ResidenceTerritory,
    resolver_id: str,
) -> ActivityAssetProjection | None:
    if territory is ResidenceTerritory.FORAL:
        return _foral_projection(resolver_id)
    if territory is ResidenceTerritory.UNRESOLVED:
        return ActivityAssetProjection(
            diagnostics=(
                CalculationSourceDiagnostic(
                    reason="activity_asset_residence_unresolved",
                    source_kind=resolver_id,
                    resolver_id=resolver_id,
                    message=(
                        "the recorded tax residence could not be read, so it is not established which rules govern "
                        "the amortization of these assets; it is outside this calculation and no figure is deducted"
                    ),
                    remedy="state the tax residence in the profile, then calculate again",
                ),
            ),
        )
    return None


def _foral_projection(resolver_id: str) -> ActivityAssetProjection:
    return ActivityAssetProjection(
        diagnostics=(
            CalculationSourceDiagnostic(
                reason="activity_asset_foral_territory",
                source_kind=resolver_id,
                resolver_id=resolver_id,
                message=(
                    "the taxpayer resides in a foral territory in this period, whose own rules govern the amortization "
                    "of these assets; it is outside this calculation and no figure is deducted"
                ),
                remedy="determine the amortization under the foral rules of your territory",
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
        if claim.amount > Decimal("0") or claim.disposal_revision_id is None
    )


def _year_history(
    history: ActivityAssetHistory,
    revision: ActivityAssetRevision,
    *,
    tax_year: int,
) -> AssetScheduleHistory:
    """Summarise history up to ``tax_year``: a later year's claim does not change this year's figure."""
    return asset_schedule_history(
        claims_through_year(history.claims, tax_year),
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
    """Which ledger rows the register withholds, and which it will not leave unexplained."""

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
      caller turns it into a non-blocking finding whose remedy is to register the element.

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
    """Project each unowned amortization row into its non-blocking finding.

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
    """Return ``(asset_id, acquisition transaction id)`` for each row of each asset's current revision.

    A superseding revision may restate the acquisition linkage, so only the
    highest revision number of each asset declares which transactions the
    register owns. Pairs are returned rather than a mapping so two assets that
    name the same transaction both keep their disposition instead of one
    silently displacing the other.
    """
    current = current_revisions(assets)
    return tuple(
        (asset_id, transaction_id)
        for asset_id in sorted(current)
        for transaction_id in current[asset_id].acquisition_transaction_ids
    )


def register_acquisition_transaction_ids(assets: tuple[ActivityAssetRevision, ...]) -> frozenset[str]:
    """Return the ledger transactions the register declares as an asset's acquisition.

    Returns:
        Every acquisition transaction id of every asset's current revision.
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
    "ActivityAssetDisposalExcess",
    "ActivityAssetDisposalObservation",
    "ActivityAssetExpenseObservation",
    "ActivityAssetProjection",
    "ActivityAssetScheduleSource",
    "LedgerExpenseRegisterClassification",
    "LedgerRentaExpenseTreatment",
    "RefusedExpenseRow",
    "RegisterOwnedAcquisition",
    "UnregisteredAmortizationRow",
    "activity_asset_disposal_excess",
    "activity_asset_disposal_excess_m131_findings",
    "activity_asset_disposal_provenance",
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
