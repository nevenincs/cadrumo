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
from typing import Final

from pydantic import BaseModel, Field

from ...core.aggregation import (
    BindingSourceKind,
    CalculationSourceLineageRole,
    LedgerIncomeGrounding,
    LedgerWithholdingDerivation,
)
from ...core.casilla_id import CasillaId
from ...core.hex import Hex64Str
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
from ...domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from ...domain.calculations.registry.ledger_renta_income_bindings import renta_income_target_casilla
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
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
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
    free_base_remains,
    m130_register_accruals,
)
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..invoices.catalogue_reads_ports import TransactionCatalogueReader
from ..user_profile.plantilla_media_rows import plantilla_media_years_of
from ..user_profile.projections import record_to_path_values
from .activity_asset_accrual_diagnostics import (
    accrual_unavailable_diagnostic,
    activity_undeclared_diagnostic,
    m130_accrual_diagnostics,
)
from .renta_ledger import resident_territory
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceProvenance

_AGRARIAN_INSTALMENT_SELECTOR: Final[str] = (
    "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras"
)
"""The activities whose instalment is a share of income under RIRPF art. 110.1.c."""

_NOT_THIS_RETURN: Final[frozenset[ResidenceTerritory]] = frozenset(
    {ResidenceTerritory.FORAL, ResidenceTerritory.UNRESOLVED},
)
"""The readings under which the register contributes nothing to a calculation."""


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

    def amortization_box(self, asset_kind: AssetKind) -> CasillaId | None:
        """Return the box this calculation's edition binds for an asset kind's amortization."""
        return activity_asset_amortization_casillas(self._context.revision).get(asset_kind)

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
    """Project effective claims into the boxes the edition binds, reporting this year's uncovered intervals.

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
    observations = _m100_claim_observations(
        history.claims, period=period, boxes=activity_asset_amortization_casillas(context.revision)
    )
    reached = {observation.target_casilla_id for observation in observations}
    forecast = _Forecast(context, operation)
    diagnostics = _m100_all_gap_diagnostics(
        current, history, tax_year=period.filing_year, reached=reached, forecast=forecast, resolver_id=resolver_id
    )
    disposed = _m100_disposals(current, tax_year=period.filing_year)
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


def _m100_all_gap_diagnostics(
    current: Mapping[str, ActivityAssetRevision],
    history: ActivityAssetHistory,
    *,
    tax_year: int,
    reached: set[CasillaId],
    forecast: _Forecast,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        diagnostic
        for asset_id in sorted(current)
        for diagnostic in _m100_gap_diagnostics(
            current[asset_id], history, tax_year=tax_year, reached=reached, forecast=forecast, resolver_id=resolver_id
        )
    )


def _m100_disposals(
    current: Mapping[str, ActivityAssetRevision], *, tax_year: int
) -> tuple[ActivityAssetRevision, ...]:
    return tuple(
        current[asset_id]
        for asset_id in sorted(current)
        if (baja := current[asset_id].disposal) is not None and baja.disposal_date.year == tax_year
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
            diagnostics.append(activity_undeclared_diagnostic(accrual.revision, resolver_id=resolver_id))
        observations.extend(_m130_observations(accrual, period=period, target_casilla_id=target_casilla_id))
        diagnostics.extend(
            m130_accrual_diagnostics(
                accrual, period=period, target_casilla_id=target_casilla_id, resolver_id=resolver_id
            )
        )
    disposed = _bajas_reached(history, period=period)
    diagnostics.extend(
        _m130_all_excess_notes(
            disposed,
            history,
            operation=operation,
            agrarian=agrarian,
            rows=rows,
            resolver_id=resolver_id,
            income_box=renta_income_target_casilla(context.revision, modelo=context.modelo),
        )
    )
    return ActivityAssetProjection(
        observations=tuple(observations),
        diagnostics=tuple(diagnostics),
        disposal_revision_ids=tuple(revision.revision_id for revision in disposed),
    )


def _m130_all_excess_notes(
    disposed: tuple[ActivityAssetRevision, ...],
    history: ActivityAssetHistory,
    *,
    operation: PinnedAuthorityOperation,
    agrarian: frozenset[TipoActividad],
    rows: Mapping[str, Transaction],
    resolver_id: str,
    income_box: CasillaId,
) -> tuple[CalculationSourceDiagnostic, ...]:
    return tuple(
        note
        for row in _m130_excess_rows(
            disposed, history, operation=operation, agrarian=agrarian, rows=rows, target_casilla_id=income_box
        )
        for note in _m130_excess_notes(row, resolver_id=resolver_id)
    )


def _m130_observations(
    accrual: M130ElementAccrual, *, period: Period, target_casilla_id: CasillaId
) -> tuple[ActivityAssetExpenseObservation, ...]:
    return tuple(
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


@dataclass(frozen=True, slots=True)
class ActivityAssetDisposalExcess:
    """What a baja the period reaches says about income: an excess, or why it cannot say."""

    revision: ActivityAssetRevision
    target_casilla_id: CasillaId
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
    target_casilla_id: CasillaId,
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
            found.append(
                ActivityAssetDisposalExcess(
                    revision=revision, target_casilla_id=target_casilla_id, agrarian=is_agrarian, error=error
                )
            )
            continue
        if amount > Decimal("0"):
            found.append(
                ActivityAssetDisposalExcess(
                    revision=revision, target_casilla_id=target_casilla_id, amount=amount, agrarian=is_agrarian
                )
            )
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
    return _m130_excess_rows(
        disposed,
        history,
        operation=operation,
        agrarian=agrarian,
        rows=rows,
        target_casilla_id=renta_income_target_casilla(context.revision, modelo=context.modelo),
    )


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
        notes.extend(self._calculation_findings(revision, calculation))
        return _BajaReading(
            observations=tuple(
                ActivityAssetDisposalObservation(revision_id=revision.revision_id, route=route, amount=amount)
                for route, amount in figures
                if route in self._routes
            ),
            notes=tuple(notes),
        )

    def _calculation_findings(
        self, revision: ActivityAssetRevision, calculation: ActivityAssetDisposalCalculation
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return tuple(
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


def _amortization_box_unbound_diagnostic(
    revision: ActivityAssetRevision,
    *,
    resolver_id: str,
) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="activity_asset_accrual_unavailable",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        message=(
            f"this edition binds no box for the amortization of {revision.asset_kind.value} assets, "
            f"so element {revision.asset_id!r} contributes nothing to this calculation"
        ),
        remedy="enter the amortization by hand on the return if it applies",
    )


def _m100_claim_observations(
    claims: tuple[AmortizationClaim, ...],
    *,
    period: Period,
    boxes: Mapping[AssetKind, CasillaId],
) -> tuple[ActivityAssetExpenseObservation, ...]:
    return tuple(
        ActivityAssetExpenseObservation(
            source=ActivityAssetClaimSource(claim_id=claim.claim_id),
            modelo="100",
            period=period.registry_token,
            target_casilla_id=boxes[claim.asset_kind],
            deductible_amount=claim.amount,
        )
        for claim in select_effective_claims(claims, tax_year=period.filing_year)
        if claim.asset_kind in boxes and (claim.amount > Decimal("0") or claim.disposal_revision_id is None)
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
    casilla = forecast.amortization_box(revision.asset_kind)
    if casilla is None:
        return (_amortization_box_unbound_diagnostic(revision, resolver_id=resolver_id),)
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
                    accrual_unavailable_diagnostic(revision, exc, casilla_id=named_box, resolver_id=resolver_id),
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


__all__ = [
    "ActivityAssetClaimSource",
    "ActivityAssetDisposalExcess",
    "ActivityAssetDisposalObservation",
    "ActivityAssetExpenseObservation",
    "ActivityAssetProjection",
    "ActivityAssetScheduleSource",
    "activity_asset_disposal_excess",
    "activity_asset_disposal_excess_m131_findings",
    "activity_asset_disposal_provenance",
    "activity_asset_provenance",
    "m100_activity_asset_projection",
    "m130_activity_asset_projection",
]
