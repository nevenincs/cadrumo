"""The importe neto de la cifra de negocios of the período impositivo inmediato anterior.

LIS art. 29.1 selects the Impuesto sobre Sociedades rate by the INCN of the
immediately preceding tax period, and art. 101 does the same for the reducida
dimensión incentives. The Modelo 200 edition of the ejercicio states where that
figure comes from once: the binding :data:`INCN_PERIODO_ANTERIOR_BINDING_ID`
copies the preceding Modelo 200's net turnover box. Every consumer that needs
the figure (the Modelo 200 rate and its verification, the Modelo 202 tipo de
gravamen and its "INCN del período impositivo inmediato anterior inferior a 1
millón" mark) reads it here, through the same previous-filing resolution and the
same operator statement the Modelo 200 calculation uses, so no consumer reads
the box or restates the period offset.

The figure resolves, in order:

1. from the held preceding return, unless the ejercicio's Modelo 200 marks a box
   the binding declares sets that return aside (the grupo mercantil mark, LIS
   art. 101.3);
2. else from the figure the filer stated for that return on the ejercicio's
   Modelo 200 calculation;
3. else, only where the caller establishes that the preceding período lasted
   twelve months, from the turnover of the twelve months before the período the
   filer states on the profile: for a twelve-month período those twelve months
   are that período itself, so the figure the law reads (art. 29.1 and 101.1,
   "período impositivo inmediato anterior") is the same. It is never read for a
   shorter preceding período (art. 101.2 raises that período's turnover to a
   year, which the twelve-month statement does not state) nor where the held
   return is set aside as a group member (art. 101.3);
4. else it stays unresolved.

It never defaults to zero: a zero lowers the rate. Where a held return and the
stated twelve-month turnover of a twelve-month preceding período disagree,
neither overrides the other: the figure stays unresolved, carrying both, and the
consumer raises the disagreement as a finding.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_prior_value_rules import set_aside_binding_ids
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.relations import RegistryFoldRequirement
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.binding_prefill import resolve_bindings_from_local_store
from ..calculations.cross_period_clean_state import attestable_carry_binding_ids
from ..calculations.cross_period_models import (
    OperatorAttestedValue,
    operator_value_attestations,
    period_strictly_before_activity_start,
)
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
from .calculation_action_ports import CalculationActionPorts
from .preconditions import ATTEST_PRIOR_VALUE_ACTION_ID
from .selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorNotFoundError,
    select_modelo_calculation_revision,
)

INCN_PERIODO_ANTERIOR_BINDING_ID: Final[BindingId] = "modelo-200-incn-periodo-impositivo-anterior"
"""The binding that carries the preceding período impositivo's INCN into a Modelo 200 ejercicio."""

_IS_ANNUAL_ROLE: Final = "sociedades.annual"
_ANNUAL_PERIOD: Final = "0A"


class IncnPeriodoAnteriorOrigin(StrEnum):
    """Where the figure came from, or why there is none."""

    HELD_RETURN = "held_return"
    """The preceding Modelo 200 the application holds shows it."""
    OPERATOR_STATEMENT = "operator_statement"
    """The filer stated it for a preceding return the application does not hold."""
    TWELVE_MONTH_STATEMENT = "twelve_month_statement"
    """The preceding período lasted twelve months, so the profile's twelve-month turnover is its own."""
    UNRESOLVED = "unresolved"
    """Neither a held return nor a statement supplies it."""


class IncnPeriodoAnteriorGap(StrEnum):
    """Why an unresolved figure stays unresolved."""

    NOT_READ_BY_EDITION = "not_read_by_edition"
    """The ejercicio's Modelo 200 edition selects no rate by the preceding turnover."""
    NO_RETURN_HELD = "no_return_held"
    """No preceding return is held and the filer stated no figure."""
    HELD_RETURN_WITHOUT_FIGURE = "held_return_without_figure"
    """A preceding return is held but does not show the figure."""
    PERIOD_BEFORE_ACTIVITY = "period_before_activity"
    """The preceding period ended before the activity began; the filer states the first period's figure."""
    CONFLICTING_STATEMENTS = "conflicting_statements"
    """The filer stated different figures for the same preceding return."""
    HELD_RETURN_SET_ASIDE = "held_return_set_aside"
    """The ejercicio's Modelo 200 marks a box under which the held return's own figure is not the one the law reads."""
    TWELVE_MONTH_STATEMENT_DISAGREES = "twelve_month_statement_disagrees"
    """The held return and the stated twelve-month turnover of a twelve-month preceding período differ."""


class IncnPeriodoAnterior(BaseModel):
    """The preceding período impositivo's INCN for one ejercicio, with its provenance.

    ``value`` is present exactly when ``origin`` is not ``UNRESOLVED``. An
    unresolved figure names its ``gap`` and, when the filer may state it,
    ``door_action_id`` is the statement action with the coordinates below as its
    arguments. A disagreement carries both figures: ``held_value`` from the held
    return and ``twelve_month_statement`` from the profile.
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int
    binding_id: BindingId
    origin: IncnPeriodoAnteriorOrigin
    value: Decimal | None = None
    source_modelo: str | None = None
    source_filing_year: int | None = None
    source_period: str | None = None
    revision_id: str
    gap: IncnPeriodoAnteriorGap | None = None
    door_action_id: str | None = None
    held_value: Decimal | None = None
    twelve_month_statement: Decimal | None = None

    @property
    def resolved(self) -> bool:
        """Whether a figure is available."""
        return self.value is not None


IncnPeriodoAnteriorReader = Callable[[Decimal | None], IncnPeriodoAnterior]
"""The figure for one ejercicio, given the twelve-month turnover when the preceding período lasted twelve months."""


@dataclass(frozen=True, slots=True)
class IncnPeriodoAnteriorStores:
    """The persisted authorities the figure is read from, all bound to one profile bucket.

    ``operation`` is the authority pinned for the caller's run, so the figure is
    read under one authority generation.
    """

    operation: PinnedAuthorityOperation
    observation_repository: CalculationObservationRepositoryProtocol
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol

    @classmethod
    def from_calculation_ports(cls, ports: CalculationActionPorts) -> IncnPeriodoAnteriorStores:
        """The stores a calculation invocation already holds."""
        return cls(
            operation=ports.operation,
            observation_repository=ports.observation_repository,
            iva_compensation_history_repository=ports.iva_compensation_history_repository,
            calculation_repository=ports.calculation_repository,
            work_unit_repository=ports.work_unit_repository,
            filing_repository=ports.filing_repository,
        )


@dataclass(frozen=True, slots=True)
class _EjercicioStatements:
    """What the ejercicio's current Modelo 200 calculations say about the figure."""

    stated: frozenset[Decimal]
    held_return_set_aside: bool


def resolve_incn_periodo_anterior(
    bucket_id: str,
    filing_year: int,
    *,
    stores: IncnPeriodoAnteriorStores,
    activity_start_date: date | None,
    twelve_month_statement: Decimal | None = None,
) -> IncnPeriodoAnterior:
    """Resolve the preceding período impositivo's INCN for the Modelo 200 ejercicio ``filing_year``.

    ``twelve_month_statement`` is the profile's turnover of the twelve months
    before the período, passed only when the caller has established that the
    preceding período lasted twelve months; ``None`` otherwise.
    """
    operation = stores.operation
    snapshot = operation.reading_snapshot(
        form_for_role(_IS_ANNUAL_ROLE, authority=operation),
        filing_year=filing_year,
        period=_ANNUAL_PERIOD,
    )
    requirement = _turnover_requirement(snapshot)
    if requirement is None:
        return IncnPeriodoAnterior(
            filing_year=filing_year,
            binding_id=INCN_PERIODO_ANTERIOR_BINDING_ID,
            origin=IncnPeriodoAnteriorOrigin.UNRESOLVED,
            revision_id=snapshot.revision.id,
            gap=IncnPeriodoAnteriorGap.NOT_READ_BY_EDITION,
        )

    def located(
        origin: IncnPeriodoAnteriorOrigin,
        *,
        value: Decimal | None = None,
        gap: IncnPeriodoAnteriorGap | None = None,
        door_action_id: str | None = None,
        held_value: Decimal | None = None,
    ) -> IncnPeriodoAnterior:
        return IncnPeriodoAnterior(
            filing_year=filing_year,
            binding_id=INCN_PERIODO_ANTERIOR_BINDING_ID,
            origin=origin,
            value=value,
            source_modelo=requirement.source_modelo,
            source_filing_year=requirement.filing_year,
            source_period=requirement.periods[0],
            revision_id=snapshot.revision.id,
            gap=gap,
            door_action_id=door_action_id,
            held_value=held_value,
            twelve_month_statement=twelve_month_statement,
        )

    statements = _ejercicio_statements(bucket_id, snapshot, requirement, stores=stores)
    if statements.held_return_set_aside:
        # The group's turnover is neither the held return's nor the entity's own twelve months.
        held: Decimal | None = None
        held_gap: IncnPeriodoAnteriorGap | None = IncnPeriodoAnteriorGap.HELD_RETURN_SET_ASIDE
    else:
        held, held_gap = _held_value(snapshot, stores=stores, activity_start_date=activity_start_date)
    outcome = _outcome_from_held_return(located, held, held_gap, twelve_month_statement)
    if outcome is None:
        outcome = _outcome_from_statements(located, statements, held_gap, twelve_month_statement)
    if outcome is not None:
        return outcome
    attestable = INCN_PERIODO_ANTERIOR_BINDING_ID in attestable_carry_binding_ids(
        snapshot,
        operation=operation,
        observation_repository=stores.observation_repository,
        filing_catalogue=stores.filing_repository.load(),
        work_catalogue=stores.work_unit_repository.load(),
        set_aside_binding_ids=(
            frozenset({INCN_PERIODO_ANTERIOR_BINDING_ID}) if statements.held_return_set_aside else frozenset()
        ),
    )
    return located(
        IncnPeriodoAnteriorOrigin.UNRESOLVED,
        gap=held_gap or IncnPeriodoAnteriorGap.NO_RETURN_HELD,
        door_action_id=ATTEST_PRIOR_VALUE_ACTION_ID if attestable else None,
    )


class _LocatedFigure(Protocol):
    """Builds the figure for one ejercicio, stamped with the preceding return it reads."""

    def __call__(
        self,
        origin: IncnPeriodoAnteriorOrigin,
        *,
        value: Decimal | None = None,
        gap: IncnPeriodoAnteriorGap | None = None,
        door_action_id: str | None = None,
        held_value: Decimal | None = None,
    ) -> IncnPeriodoAnterior: ...


def _outcome_from_held_return(
    located: _LocatedFigure,
    held: Decimal | None,
    held_gap: IncnPeriodoAnteriorGap | None,
    twelve_month_statement: Decimal | None,
) -> IncnPeriodoAnterior | None:
    """The figure a held return settles, or ``None`` when it settles nothing."""
    if held is not None:
        if twelve_month_statement is not None and twelve_month_statement != held:
            return located(
                IncnPeriodoAnteriorOrigin.UNRESOLVED,
                gap=IncnPeriodoAnteriorGap.TWELVE_MONTH_STATEMENT_DISAGREES,
                held_value=held,
            )
        return located(IncnPeriodoAnteriorOrigin.HELD_RETURN, value=held)
    if held_gap is IncnPeriodoAnteriorGap.HELD_RETURN_WITHOUT_FIGURE:
        return located(IncnPeriodoAnteriorOrigin.UNRESOLVED, gap=held_gap)
    return None


def _outcome_from_statements(
    located: _LocatedFigure,
    statements: _EjercicioStatements,
    held_gap: IncnPeriodoAnteriorGap | None,
    twelve_month_statement: Decimal | None,
) -> IncnPeriodoAnterior | None:
    """The figure the filer's statements settle once no held return does, or ``None`` when they settle nothing."""
    if len(statements.stated) == 1:
        (value,) = statements.stated
        return located(IncnPeriodoAnteriorOrigin.OPERATOR_STATEMENT, value=value)
    if statements.stated:
        return located(IncnPeriodoAnteriorOrigin.UNRESOLVED, gap=IncnPeriodoAnteriorGap.CONFLICTING_STATEMENTS)
    if twelve_month_statement is not None and held_gap is None:
        return located(IncnPeriodoAnteriorOrigin.TWELVE_MONTH_STATEMENT, value=twelve_month_statement)
    return None


def incn_periodo_anterior_reader(
    bucket_id: str,
    filing_year: int,
    *,
    stores: IncnPeriodoAnteriorStores,
    activity_start_date: date | None,
) -> IncnPeriodoAnteriorReader:
    """Bind :func:`resolve_incn_periodo_anterior` to one ejercicio, leaving only the twelve-month turnover to give."""

    def read(twelve_month_statement: Decimal | None) -> IncnPeriodoAnterior:
        return resolve_incn_periodo_anterior(
            bucket_id,
            filing_year,
            stores=stores,
            activity_start_date=activity_start_date,
            twelve_month_statement=twelve_month_statement,
        )

    return read


def _turnover_requirement(snapshot: RegistrySnapshot) -> RegistryFoldRequirement | None:
    """The earlier filing the turnover binding reads, or ``None`` when the edition declares no such binding."""
    return next(
        (
            requirement
            for requirement in previous_filing_observation_requirements(
                snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
            )
            if INCN_PERIODO_ANTERIOR_BINDING_ID in requirement.binding_ids
        ),
        None,
    )


def _held_value(
    snapshot: RegistrySnapshot,
    *,
    stores: IncnPeriodoAnteriorStores,
    activity_start_date: date | None,
) -> tuple[Decimal | None, IncnPeriodoAnteriorGap | None]:
    """Resolve the binding from held returns exactly as the calculation does, alone among the carries."""
    others = frozenset(
        binding.id for binding in snapshot.revision.bindings if binding.id != INCN_PERIODO_ANTERIOR_BINDING_ID
    )
    try:
        report = resolve_bindings_from_local_store(
            snapshot,
            operation=stores.operation,
            repository=stores.observation_repository,
            iva_history_repository=stores.iva_compensation_history_repository,
            activity_start_date=activity_start_date,
            excluded_binding_ids=others,
        )
    except RegistryValidationError:
        return None, IncnPeriodoAnteriorGap.HELD_RETURN_WITHOUT_FIGURE
    value = report.binding_values.get(INCN_PERIODO_ANTERIOR_BINDING_ID)
    if value is not None:
        return value, None
    if any(
        INCN_PERIODO_ANTERIOR_BINDING_ID in item.binding_ids for item in _before_activity(snapshot, activity_start_date)
    ):
        return None, IncnPeriodoAnteriorGap.PERIOD_BEFORE_ACTIVITY
    return None, None


def _before_activity(
    snapshot: RegistrySnapshot, activity_start_date: date | None
) -> tuple[RegistryFoldRequirement, ...]:
    if activity_start_date is None:
        return ()
    return tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period
        )
        if requirement.filing_periods
        and all(
            period_strictly_before_activity_start(period, activity_start_date) for period in requirement.filing_periods
        )
    )


def _ejercicio_statements(
    bucket_id: str,
    snapshot: RegistrySnapshot,
    requirement: RegistryFoldRequirement,
    *,
    stores: IncnPeriodoAnteriorStores,
) -> _EjercicioStatements:
    """The figures stated, and the set-aside marks made, on this ejercicio's current Modelo 200 calculations."""
    calculation_catalogue = stores.calculation_repository.load(operation=stores.operation)
    stated: set[Decimal] = set()
    set_aside = False
    for work_unit in stores.work_unit_repository.load().work_units.values():
        if not _is_ejercicio_work(work_unit, bucket_id, snapshot):
            continue
        try:
            selection = select_modelo_calculation_revision(
                work_unit,
                selector=ModeloCalculationRevisionSelector.CURRENT,
                calculation_repository=stores.calculation_repository,
                operation=stores.operation,
                calculation_catalogue=calculation_catalogue,
            )
        except ModeloCalculationRevisionSelectorNotFoundError:
            continue
        if INCN_PERIODO_ANTERIOR_BINDING_ID in set_aside_binding_ids(
            snapshot.revision, selection.revision.casilla_values
        ):
            set_aside = True
        attestation = operator_value_attestations(selection.revision).get(INCN_PERIODO_ANTERIOR_BINDING_ID)
        if attestation is None or not _covers(attestation, requirement):
            continue
        stated.add(Decimal(attestation.value))
    return _EjercicioStatements(stated=frozenset(stated), held_return_set_aside=set_aside)


def _is_ejercicio_work(work_unit: WorkUnit, bucket_id: str, snapshot: RegistrySnapshot) -> bool:
    return (
        work_unit.bucket_id == bucket_id
        and str(work_unit.modelo) == snapshot.modelo.id
        and work_unit.filing_year == snapshot.filing_year
        and work_unit.period.registry_token == snapshot.period
    )


def _covers(attestation: OperatorAttestedValue, requirement: RegistryFoldRequirement) -> bool:
    return attestation.covers(
        source_modelo=requirement.source_modelo,
        filing_year=requirement.filing_year,
        period_token=requirement.periods[0],
    )


__all__ = [
    "INCN_PERIODO_ANTERIOR_BINDING_ID",
    "IncnPeriodoAnterior",
    "IncnPeriodoAnteriorGap",
    "IncnPeriodoAnteriorOrigin",
    "IncnPeriodoAnteriorReader",
    "IncnPeriodoAnteriorStores",
    "incn_periodo_anterior_reader",
    "resolve_incn_periodo_anterior",
]
