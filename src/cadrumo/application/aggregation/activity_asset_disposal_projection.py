"""Project Modelo 100 activity-asset disposals onto the edition's routes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.hashing import content_hash_hex
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.actividad_asset_disposal_bindings import (
    ELEMENT_ROW_ROUTES,
    ActivityAssetDisposalRoute,
    ActivityAssetDisposalRowField,
    activity_asset_disposal_route_casillas,
    activity_asset_disposal_row_binding_ids,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.irpf_regimes import irpf_estimation_regime_objetiva_token
from ...domain.calculations.row_source_identity import RowSourceIdentity
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.renta.actividad_asset.disposal import (
    BAJA_WITHOUT_TRANSMISSION_REASONS,
    TRANSMISSION_REASONS,
    ActivityAssetDisposalCalculation,
    ActivityAssetDisposalFinding,
    ActivityAssetDisposalFindingKind,
    ActivityAssetDisposalReason,
)
from ...domain.renta.actividad_asset.errors import ActividadAssetError, ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ..actividad_asset.disposal_calculation import (
    calculate_element_disposal,
    disposal_excess_applies,
    pinned_disposal_bounds,
)
from ..actividad_asset.history import ActivityAssetHistory
from ..invoices.catalogue_reads_ports import TransactionCatalogueReader
from ..user_profile.projections import record_to_path_values
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic

_AGRARIAN_INSTALMENT_SELECTOR: Final[str] = (
    "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras"
)


@dataclass(frozen=True, slots=True)
class ActivityAssetDisposalObservation:
    """One figure of a baja on its way to the box the revision gives its route."""

    revision_id: str
    route: ActivityAssetDisposalRoute
    amount: Decimal


def calculate_asset_disposal(
    revision: ActivityAssetRevision,
    history: ActivityAssetHistory,
    *,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetDisposalCalculation:
    """Calculate a recorded disposal using the pinned authority bounds."""
    disposal = revision.disposal
    if disposal is None:  # defensive: callers select revisions with a baja
        raise ActividadAssetValidationError(translated_message="ledger.actividad_asset.errors.disposal_not_recorded")
    return calculate_element_disposal(revision, disposal, history, bounds=pinned_disposal_bounds(operation))


def asset_disposal_finding(
    revision: ActivityAssetRevision,
    message: str,
    sentence: CalculationNoteSentence,
    /,
    *,
    resolver_id: str,
    **values: object,
) -> CalculationSourceDiagnostic:
    """Describe a disposal finding with its structured source and facts."""
    disposal = revision.disposal
    return CalculationSourceDiagnostic(
        reason="activity_asset_disposal_finding",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=f"activity-asset:{revision.asset_id}",
        message=f"baja of element {revision.asset_id!r}: {message}",
        fact=CalculationNoteFact(
            sentence=sentence,
            element_refs=(revision.asset_id,),
            values=tuple(
                sorted(
                    (key, str(value))
                    for key, value in {
                        **values,
                        "date": "" if disposal is None else disposal.disposal_date.isoformat(),
                    }.items()
                )
            ),
        ),
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
            asset_disposal_finding(
                revision,
                f"{message}, so activity income may be understated",
                CalculationNoteSentence.DISPOSAL_UNRESOLVED_INCOME,
                resolver_id=resolver_id,
            ),
        )
    return (
        asset_disposal_finding(
            revision,
            f"{message}; no box carries it",
            CalculationNoteSentence.DISPOSAL_UNRESOLVED_NO_BOX,
            resolver_id=resolver_id,
        ),
    )


@dataclass(frozen=True, slots=True)
class ActivityAssetDisposalRow:
    """A gain or loss that fills a row of the form, with what a row of its own states."""

    revision: ActivityAssetRevision
    route: ActivityAssetDisposalRoute
    amount: Decimal
    calculation: ActivityAssetDisposalCalculation
    acquisition_date: date | None = None

    @property
    def source_identity(self) -> str:
        """Identify the sale the row comes from."""
        return f"activity-asset:{self.revision.asset_id}:{self.revision.revision_id}"

    def column(self, row_field: ActivityAssetDisposalRowField) -> Decimal | str | bool | None:
        """Return this sale's value for a column; the clave column is the revision's own."""
        disposal = self.revision.disposal
        loss = self.amount if self.route is ActivityAssetDisposalRoute.TRANSMISSION_LOSS_ELEMENT else None
        gain = self.amount if self.route is ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT else None
        match row_field:
            case ActivityAssetDisposalRowField.TRANSMISSION_DATE:
                return None if disposal is None else disposal.disposal_date.isoformat()
            case ActivityAssetDisposalRowField.ACQUISITION_DATE:
                return None if self.acquisition_date is None else self.acquisition_date.isoformat()
            case ActivityAssetDisposalRowField.ONEROUS_TRANSFER:
                return True if disposal is not None and disposal.reason in TRANSMISSION_REASONS else None
            case ActivityAssetDisposalRowField.TRANSMISSION_VALUE:
                return self.calculation.net_transmission_value
            case ActivityAssetDisposalRowField.ACQUISITION_VALUE:
                return self.calculation.net_value
            case ActivityAssetDisposalRowField.GAIN | ActivityAssetDisposalRowField.GAIN_DIFFERENCE:
                return gain
            case ActivityAssetDisposalRowField.LOSS | ActivityAssetDisposalRowField.LOSS_DIFFERENCE:
                return loss
            case _:
                return None


def disposal_row_source_identities(
    identities: Mapping[tuple[BindingId, int], str],
    rows: Sequence[ActivityAssetDisposalRow],
) -> dict[tuple[BindingId, int], RowSourceIdentity]:
    """Fingerprint each row coordinate by what its sale states."""
    fingerprints = {
        row.source_identity: content_hash_hex(
            {
                "identity": row.source_identity,
                "route": row.route.value,
                "amount": str(row.amount),
                "transmission_date": str(row.column(ActivityAssetDisposalRowField.TRANSMISSION_DATE)),
                "acquisition_date": str(row.acquisition_date),
                "transmission_value": str(row.calculation.transmission_value),
                "transmission_costs": str(row.calculation.transmission_costs),
                "net_value": str(row.calculation.net_value),
            }
        )
        for row in rows
    }
    return {
        key: RowSourceIdentity(
            source_kind=BindingSourceKind.ACTIVITY_ASSET_DISPOSAL,
            source_row_identity=identity,
            fingerprint=fingerprints[identity],
        )
        for key, identity in identities.items()
    }


@dataclass(frozen=True, slots=True)
class _BajaReading:
    observations: tuple[ActivityAssetDisposalObservation, ...] = ()
    notes: tuple[CalculationSourceDiagnostic, ...] = ()
    row_figures: tuple[ActivityAssetDisposalRow, ...] = ()


class ActivityAssetBajaReader:
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
        """Bind the calculation context and the evidence used by the reader."""
        self._context = context
        self._operation = operation
        self._period = period
        self._transactions = transactions
        self._resolver_id = resolver_id
        self._routes = activity_asset_disposal_route_casillas(context.revision)

    def read(self, revision: ActivityAssetRevision, history: ActivityAssetHistory) -> _BajaReading:
        """Resolve one disposal into bound figures and findings."""
        try:
            calculation = calculate_asset_disposal(revision, history, operation=self._operation)
        except (ActividadAssetError, RegistryError) as error:
            return _BajaReading(notes=_m100_unresolved_disposal(revision, error, resolver_id=self._resolver_id))
        figures, notes = self._figures(revision, calculation)
        notes.extend(self._figure_finding(revision, route, amount, calculation) for route, amount in figures)
        notes.extend(self._calculation_findings(revision, calculation))
        return _BajaReading(
            observations=tuple(
                ActivityAssetDisposalObservation(revision_id=revision.revision_id, route=route, amount=amount)
                for route, amount in figures
                if route in self._routes
            ),
            notes=tuple(notes),
            row_figures=tuple(
                ActivityAssetDisposalRow(
                    revision=revision,
                    route=route,
                    amount=amount,
                    calculation=calculation,
                    acquisition_date=self._acquisition_date(revision),
                )
                for route, amount in figures
                if route in ELEMENT_ROW_ROUTES or route in _PROPERTY_ROW_ROUTES
            ),
        )

    def read_all(self, revisions: Iterable[ActivityAssetRevision], history: ActivityAssetHistory) -> _BajaReading:
        """Read the disposals together and retain the element rows the form can repeat."""
        readings = tuple(self.read(revision, history) for revision in revisions)
        return _BajaReading(
            observations=tuple(item for reading in readings for item in reading.observations),
            notes=(
                *(note for reading in readings for note in reading.notes),
                *self.shared_row_findings(readings),
            ),
            row_figures=tuple(
                figure for reading in readings for figure in reading.row_figures if figure.route in ELEMENT_ROW_ROUTES
            ),
        )

    def _acquisition_date(self, revision: ActivityAssetRevision) -> date | None:
        """Return the day the element was acquired: stated on it, or the day of its acquisition row."""
        if revision.declared_acquisition_date is not None:
            return revision.declared_acquisition_date
        row = revision.acquisition_row_in(self._transactions.load().transactions)
        return None if row is None else transaction_filing_date(row)

    def _figures(
        self, revision: ActivityAssetRevision, calculation: ActivityAssetDisposalCalculation
    ) -> tuple[list[tuple[ActivityAssetDisposalRoute, Decimal]], list[CalculationSourceDiagnostic]]:
        figures: list[tuple[ActivityAssetDisposalRoute, Decimal]] = []
        notes: list[CalculationSourceDiagnostic] = []
        if calculation.route_changed_by_later_affectation:
            notes.append(
                self._finding(
                    revision,
                    _later_affectation_message(calculation),
                    CalculationNoteSentence.DISPOSAL_LATER_AFFECTATION,
                    amount=calculation.result,
                )
            )
        elif (route := _result_route(revision, calculation)) is not None and calculation.result is not None:
            figures.append((route, abs(calculation.result)))
        elif calculation.result == Decimal("0"):
            notes.append(
                self._finding(
                    revision,
                    "the sale neither gains nor loses, so no box carries it",
                    CalculationNoteSentence.DISPOSAL_ZERO_RESULT,
                    transmission_value=calculation.net_transmission_value,
                    net_value=calculation.net_value,
                )
            )
        if calculation.excess > Decimal("0"):
            excess_route = self._excess_route(revision)
            if excess_route is None:
                notes.append(
                    self._finding(
                        revision,
                        f"{calculation.excess} EUR of excess in an agrarian activity under modulos has no established "
                        "line; it is left to you",
                        CalculationNoteSentence.DISPOSAL_MODULES_AGRARIAN_EXCESS,
                        amount=calculation.excess,
                    ),
                )
            else:
                figures.append((excess_route, calculation.excess))
        return figures, notes

    def shared_row_findings(self, readings: Iterable[_BajaReading]) -> tuple[CalculationSourceDiagnostic, ...]:
        """Say what each sale would state on a row of its own when several share one.

        The official form repeats these rows, one per element. An edition that declares row
        columns gives each sale of an element its own; every other family holds one value
        per box. The total stays right, as the form's own sums need, but such a row can no
        longer be read as one sale, so each sale's date and values are put in front of the
        filer.

        Returns:
            One finding per sale of a row family two or more sales fill with no row of their own.
        """
        figures = tuple(figure for reading in readings for figure in reading.row_figures)
        has_element_rows = bool(activity_asset_disposal_row_binding_ids(self._context.revision))
        return tuple(
            self._shared_row_finding(figure, count=len(family))
            for routes in (() if has_element_rows else (ELEMENT_ROW_ROUTES,)) + (_PROPERTY_ROW_ROUTES,)
            if len(family := tuple(item for item in figures if item.route in routes)) > 1
            for figure in family
            if figure.route in self._routes
        )

    def _shared_row_finding(self, figure: ActivityAssetDisposalRow, *, count: int) -> CalculationSourceDiagnostic:
        calculation = figure.calculation
        return self._finding(
            figure.revision,
            f"{count} sales share one row of box {self._routes[figure.route]}, where the form gives each its own; "
            f"this one comes to {figure.amount} EUR",
            CalculationNoteSentence.DISPOSAL_SHARED_ROW,
            count=count,
            amount=figure.amount,
            box=self._routes[figure.route],
            transmission_value=calculation.net_transmission_value,
            net_value=calculation.net_value,
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
                _FINDING_SENTENCES[finding.kind],
                **_finding_values(finding),
            )
            for finding in calculation.findings
        )

    def _finding(
        self, revision: ActivityAssetRevision, message: str, sentence: CalculationNoteSentence, /, **values: object
    ) -> CalculationSourceDiagnostic:
        return asset_disposal_finding(revision, message, sentence, resolver_id=self._resolver_id, **values)

    def _figure_finding(
        self,
        revision: ActivityAssetRevision,
        route: ActivityAssetDisposalRoute,
        amount: Decimal,
        calculation: ActivityAssetDisposalCalculation,
    ) -> CalculationSourceDiagnostic:
        box = self._routes.get(route)
        if box is None:
            return self._finding(
                revision,
                f"{amount} EUR ({route.value}) reaches no box of this edition",
                CalculationNoteSentence.DISPOSAL_FIGURE_NO_BOX,
                amount=amount,
            )
        message = f"{amount} EUR ({route.value}) enters box {box}{self._row_entry(route)}"
        if route in ELEMENT_ROW_ROUTES or route in _PROPERTY_ROW_ROUTES:
            return self._finding(
                revision,
                message,
                (
                    CalculationNoteSentence.DISPOSAL_FIGURE_ELEMENT_ROW
                    if route in ELEMENT_ROW_ROUTES
                    else CalculationNoteSentence.DISPOSAL_FIGURE_PROPERTY_ROW
                ),
                amount=amount,
                box=box,
                transmission_value=calculation.net_transmission_value,
                net_value=calculation.net_value,
            )
        return self._finding(revision, message, CalculationNoteSentence.DISPOSAL_FIGURE_IN_BOX, amount=amount, box=box)

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


_FINDING_SENTENCES: Final[Mapping[ActivityAssetDisposalFindingKind, CalculationNoteSentence]] = MappingProxyType(
    {
        ActivityAssetDisposalFindingKind.CLAIM_GAP: CalculationNoteSentence.DISPOSAL_CLAIM_GAP,
        ActivityAssetDisposalFindingKind.MINIMUM_EXCEEDED_DEDUCTION: (
            CalculationNoteSentence.DISPOSAL_MINIMUM_EXCEEDED_DEDUCTION
        ),
        ActivityAssetDisposalFindingKind.NO_MINIMUM_AUTHORITY: CalculationNoteSentence.DISPOSAL_NO_MINIMUM_AUTHORITY,
        ActivityAssetDisposalFindingKind.MINIMUM_UNRESOLVED: CalculationNoteSentence.DISPOSAL_MINIMUM_UNRESOLVED,
        ActivityAssetDisposalFindingKind.EXEMPTION_NOT_COMPUTED: (
            CalculationNoteSentence.DISPOSAL_EXEMPTION_NOT_COMPUTED
        ),
    },
)
"""The sentence that states each thing a baja's calculation tells the filer."""


def _finding_values(finding: ActivityAssetDisposalFinding) -> dict[str, object]:
    return {
        **({} if finding.tax_year is None else {"year": finding.tax_year}),
        **({} if finding.effect_on_cost is None else {"effect": finding.effect_on_cost}),
    }


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


__all__ = [
    "ActivityAssetBajaReader",
    "ActivityAssetDisposalObservation",
    "asset_disposal_finding",
    "calculate_asset_disposal",
]
