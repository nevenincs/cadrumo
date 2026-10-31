"""Read-only Modelo 100/130 projections of the activity-asset register.

Modelo 100 carries effective claims only. Modelo 130 carries what each element
accrued from 1 January to the quarter's end, worked out from its schedule without
recording anything (RIRPF art. 110.1.a); an element on a free method has no
computable accrual, so it contributes its effective claims. Neither creates a
charge. The register is the only route to the activity amortization boxes: a
ledger row in an amortization category is acquisition evidence, withheld when the
register owns it and a non-blocking finding when it does not.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from ...domain.calculations.registry.ledger_renta_income_bindings import renta_income_target_casilla
from ...domain.contribuyente.tax_residence import ResidenceTerritory
from ...domain.modelos.calculation_revision_sources import (
    ACTIVITY_ASSET_CLAIM_REF_PREFIX,
    ACTIVITY_ASSET_DISPOSAL_FIGURES_REF_PREFIX,
    ACTIVITY_ASSET_DISPOSAL_REF_PREFIX,
    ACTIVITY_ASSET_SCHEDULE_REF_PREFIX,
    CalculationNoteFact,
    CalculationNoteSentence,
)
from ...domain.renta.actividad_asset.claims import (
    AmortizationClaim,
    current_revisions,
    select_effective_claims,
)
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ..actividad_asset.disposal_calculation import (
    disposal_calculation_digest,
    disposal_excess_applies,
    pinned_disposal_bounds,
)
from ..actividad_asset.history import ActivityAssetHistory
from ..actividad_asset.schedule_walk import (
    M100GapKind,
    M130ElementAccrual,
    m100_claim_gaps,
    m130_register_accruals,
)
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..invoices.catalogue_reads_ports import TransactionCatalogueReader
from ..user_profile.plantilla_media_rows import plantilla_media_years_of
from .activity_asset_accrual_diagnostics import (
    accrual_unavailable_diagnostic,
    activity_undeclared_diagnostic,
    m130_accrual_diagnostics,
)
from .activity_asset_disposal_projection import (
    ActivityAssetBajaReader,
    ActivityAssetDisposalObservation,
    ActivityAssetDisposalRow,
    asset_disposal_finding,
    calculate_asset_disposal,
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
    period: str = Field(min_length=1, max_length=16)
    target_casilla_id: CasillaId
    deductible_amount: Decimal = Field(ge=Decimal("0"))


@dataclass(frozen=True, slots=True)
class ActivityAssetProjection:
    """What the register contributes to one calculation, and what it has to say about it."""

    observations: tuple[ActivityAssetExpenseObservation, ...] = ()
    diagnostics: tuple[CalculationSourceDiagnostic, ...] = ()
    disposal_revision_ids: tuple[str, ...] = ()
    disposal_digests: tuple[str, ...] = ()
    disposal_observations: tuple[ActivityAssetDisposalObservation, ...] = ()
    disposal_rows: tuple[ActivityAssetDisposalRow, ...] = ()


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
    reader = ActivityAssetBajaReader(
        context, operation, period=period, transactions=transactions, resolver_id=resolver_id
    )
    bajas = reader.read_all(disposed, history)
    return ActivityAssetProjection(
        observations=observations,
        diagnostics=(
            *_residence_period_findings(territory, period=period, resolver_id=resolver_id),
            *diagnostics,
            *bajas.notes,
        ),
        disposal_revision_ids=tuple(revision.revision_id for revision in disposed),
        disposal_digests=_disposal_digests(disposed, history, operation=operation),
        disposal_observations=bajas.observations,
        disposal_rows=bajas.row_figures,
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
        disposal_digests=_disposal_digests(disposed, history, operation=operation),
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
            amount = calculate_asset_disposal(revision, history, operation=operation).excess
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


def _disposal_digests(
    disposed: tuple[ActivityAssetRevision, ...],
    history: ActivityAssetHistory,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[str, ...]:
    bounds = pinned_disposal_bounds(operation)
    return tuple(
        disposal_calculation_digest(revision, revision.disposal, history, bounds=bounds)
        for revision in disposed
        if revision.disposal is not None
    )


def _m130_excess_notes(
    row: ActivityAssetDisposalExcess,
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    if row.error is not None:
        return (
            asset_disposal_finding(
                row.revision,
                f"its excess could not be worked out ({row.error}), so this instalment carries none",
                CalculationNoteSentence.DISPOSAL_INSTALMENT_EXCESS_UNRESOLVED,
                resolver_id=resolver_id,
            ),
        )
    if row.agrarian:
        return (
            asset_disposal_finding(
                row.revision,
                f"{row.amount} EUR of excess in an agrarian activity has no established instalment line; "
                "it is left to you",
                CalculationNoteSentence.DISPOSAL_INSTALMENT_AGRARIAN_EXCESS,
                resolver_id=resolver_id,
                amount=row.amount,
            ),
        )
    return ()


def activity_asset_disposal_excess_m131_findings(
    excess: tuple[ActivityAssetDisposalExcess, ...],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Say that an excess reaches no Modelo 131 line, whose instructions are silent on it.

    An excess that could not be worked out is said too, as Modelos 100 and 130 say it:
    the income it could add is no less the filer's to account for.

    Returns:
        One non-blocking finding per excess.
    """
    return tuple(_m131_excess_finding(row, resolver_id=resolver_id) for row in excess)


def _m131_excess_finding(row: ActivityAssetDisposalExcess, *, resolver_id: str) -> CalculationSourceDiagnostic:
    if row.error is not None:
        return asset_disposal_finding(
            row.revision,
            f"its excess could not be worked out ({row.error}), and Modelo 131, whose instructions do not address "
            "it, carries none",
            CalculationNoteSentence.DISPOSAL_M131_EXCESS_UNRESOLVED,
            resolver_id=resolver_id,
        )
    return asset_disposal_finding(
        row.revision,
        f"{row.amount} EUR of excess is not routed to Modelo 131, whose instructions do not address it",
        CalculationNoteSentence.DISPOSAL_M131_EXCESS,
        resolver_id=resolver_id,
        amount=row.amount,
    )


def activity_asset_disposal_provenance(
    projection: ActivityAssetProjection,
    *,
    resolver_id: str,
    resolved_binding_source: BindingSourceKind,
) -> tuple[CalculationSourceProvenance, ...]:
    """Name each baja a calculation's period reaches and what its figures came to, which the drift gate compares.

    Returns:
        Two primary provenance rows per baja.
    """
    source_refs = (
        *(f"{ACTIVITY_ASSET_DISPOSAL_REF_PREFIX}{revision_id}" for revision_id in projection.disposal_revision_ids),
        *(f"{ACTIVITY_ASSET_DISPOSAL_FIGURES_REF_PREFIX}{digest}" for digest in projection.disposal_digests),
    )
    return tuple(
        CalculationSourceProvenance(
            resolver_id=resolver_id,
            resolved_binding_source=resolved_binding_source,
            contributor_source_kind=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL.value,
            contributor_binding_source=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=source_ref,
            parent_source_ref=None,
            terminal_origin=TerminalOriginClass.LEDGER_AGGREGATE,
        )
        for source_ref in source_refs
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
            fact=CalculationNoteFact.of(
                CalculationNoteSentence.RESIDENCE_PERIOD_UNKNOWN, date=period.end_date.isoformat()
            ),
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
        fact=CalculationNoteFact.of(CalculationNoteSentence.AMORTIZATION_BOX_UNBOUND, elements=(revision.asset_id,)),
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
    for gap in m100_claim_gaps(revision, history, forecast=forecast, tax_year=tax_year):
        if gap.error is not None:
            diagnostics.append(
                accrual_unavailable_diagnostic(revision, gap.error, casilla_id=named_box, resolver_id=resolver_id),
            )
            continue
        if gap.kind is M100GapKind.FREE_METHOD:
            accrued = "no computable accrual, because the amount of a free method is the taxpayer's election"
            fact = CalculationNoteFact.of(
                CalculationNoteSentence.CLAIM_GAP_FREE_METHOD,
                elements=(revision.asset_id,),
                start=gap.covered_from.isoformat(),
                end=(gap.covered_until - timedelta(days=1)).isoformat(),
                box=casilla,
            )
        else:
            accrued = f"{gap.accrued} EUR accrued"
            fact = CalculationNoteFact.of(
                CalculationNoteSentence.CLAIM_GAP_ACCRUED,
                elements=(revision.asset_id,),
                start=gap.covered_from.isoformat(),
                end=(gap.covered_until - timedelta(days=1)).isoformat(),
                amount=gap.accrued,
                box=casilla,
            )
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
                fact=fact,
            ),
        )
    return tuple(diagnostics)


__all__ = [
    "ActivityAssetClaimSource",
    "ActivityAssetDisposalExcess",
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
