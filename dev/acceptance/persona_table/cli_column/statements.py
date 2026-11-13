"""What the table states about a return around its calculation, as plain statements the CLI column can make itself.

The table states these facts in process by submitting registered operations, in the order of the planner's
``prepare_return`` and the lifecycle's ``_calculate``. This module reads the same persona facts with the same public
readers, in the same order, and writes them down as :class:`Statement` records; it submits nothing and writes no
store. It runs in the world's own interpreter, where the pinned authority and the profile are open, so the report
that leaves it carries everything the driver needs and the driver reads no product code.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Final

from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_origin_columns,
)
from cadrumo.domain.contribuyente.inmueble_facts import inmuebles_from_facts
from cadrumo.entrypoints.tests.persona_materialisation import (
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    attested_before_calculating,
    load_profile_record,
)
from cadrumo.entrypoints.tests.persona_prior_values import entries_on
from cadrumo.entrypoints.tests.persona_work_inputs import WorkInputError, resolved_casillas, work_inputs_for
from cadrumo.tests.personas import AttestedPriorValue, Persona, PriorCarries, RentalProperty, YearEnvelope

from ..rows import PlannedRow
from .world_report import Phase, Statement, StatementKind

_MODELO_100: Final = "100"
_CANONICAL_AMOUNT: Final = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?")
"""What ``attest-prior-carries --amount`` reads after the box: a positive amount of at most two decimals."""


def plain_amount(amount: Decimal) -> str:
    """``amount`` as the plain decimal text a command reads, without an exponent or trailing zeros."""
    return format(amount.normalize(), "f") if amount else "0"


def carry_amount(box: str, amount: Decimal) -> tuple[str, str] | str | None:
    """``(box, text)`` for a positive amount the command can state, ``None`` for a zero, else why it cannot be said.

    A zero pending carry is the statement of no amount, which is what the command states for every carry it is given
    no amount for.
    """
    if amount == 0:
        return None
    text = plain_amount(amount)
    if amount < 0 or _CANONICAL_AMOUNT.fullmatch(text) is None:
        return f"box {box} states {text}; the command reads a positive amount of at most two decimals"
    return (box, text)


def stated_amounts(items: Sequence[PriorCarries]) -> tuple[tuple[tuple[str, str], ...], str | None]:
    """The ``(box, text)`` of each amount the persona states pending, and why the command cannot say them all, if so."""
    stated = [carry_amount(box, amount) for item in items for box, amount in item.pending]
    gaps = [each for each in stated if isinstance(each, str)]
    return tuple(each for each in stated if isinstance(each, tuple)), "; ".join(gaps) or None


def carry_statements(
    carries: Sequence[PriorCarries], envelope: YearEnvelope, plan: PlannedRow
) -> tuple[Statement, ...]:
    """The one statement of the persona's pending carries on the Modelo 100 of the plan's year, or none.

    The command states every open family in one edit, so the persona's families travel together.
    """
    items = [item for item in carries if item.year.resolve(envelope) == plan.year]
    if plan.modelo != _MODELO_100 or not items:
        return ()
    amounts, gap = stated_amounts(items)
    families = tuple(dict.fromkeys(item.family for item in items))
    return (Statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, families=families, amounts=amounts, gap=gap),)


def declared_entries(
    world: PersonaWorld, plan: PlannedRow, entries: Sequence[AttestedPriorValue]
) -> tuple[AttestedPriorValue, ...]:
    """``entries`` less those stating ``where_declared`` for a return whose edition does not declare their binding.

    The table skips such an entry without a refusal, so the CLI column does not state a binding the edition lacks.
    An entry without the flag is kept whatever the edition declares, and a return the registry selects no edition
    for keeps every entry, left to its own calculation refusal.
    """
    if not any(entry.where_declared for entry in entries):
        return tuple(entries)
    try:
        revision = world.operation.revision_for_context(plan.modelo, filing_year=plan.year, period=plan.period)
    except RegistryError:
        return tuple(entries)
    declared = revision_bindings_by_id(revision)
    return tuple(entry for entry in entries if not entry.where_declared or entry.binding in declared)


def prior_value_statements(world: PersonaWorld, plan: PlannedRow) -> tuple[Statement, ...]:
    """The figures the persona attests for the return: before its first calculation where the table states them so.

    The table also states them after every calculation, where the application offers it, so the statements follow
    again in that phase. An entry that states ``where_declared`` is left out of a return whose edition lacks its
    binding.
    """
    entries = declared_entries(
        world,
        plan,
        entries_on(
            world.attested_prior_values, world.envelope, modelo=plan.modelo, filing_year=plan.year, period=plan.period
        ),
    )
    before = attested_before_calculating(world, modelo=plan.modelo, year=plan.year, period=plan.period)
    phases = (Phase.BEFORE_EVIDENCE, Phase.AFTER_CALCULATION) if before else (Phase.AFTER_CALCULATION,)
    return tuple(
        Statement(StatementKind.PRIOR_VALUE, phase, target=entry.binding, value=plain_amount(entry.value))
        for phase in phases
        for entry in entries
    )


def work_input_statements(world: PersonaWorld, plan: PlannedRow) -> tuple[Statement, ...]:
    """The casilla values the persona's operator types on the return before its first calculation.

    Each role is typed on the casilla it names in the edition the law selects; a role that edition lacks is not
    typed, and a return the registry selects no edition for is left to its own calculation refusal.
    """
    entry = work_inputs_for(world.work_inputs, world.envelope, modelo=plan.modelo, year=plan.year, period=plan.period)
    if entry is None:
        return ()
    try:
        revision = world.operation.revision_for_context(plan.modelo, filing_year=plan.year, period=plan.period)
    except RegistryError:
        return ()
    try:
        casillas = resolved_casillas(revision, entry, where=f"Modelo {plan.modelo} {plan.year} {plan.period}")
    except WorkInputError as error:
        return (Statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, refusal=str(error)),)
    return tuple(
        Statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, target=casilla, value=_decimal_text(amount))
        for casilla, amount in casillas
    )


def _decimal_text(amount: str) -> str:
    try:
        return plain_amount(Decimal(amount))
    except InvalidOperation:
        return amount


def work_income_statements(world: PersonaWorld, plan: PlannedRow) -> tuple[Statement, ...]:
    """The persona's statement that the work income of a Modelo 100's ejercicio is none, made after its calculation."""
    stated = plan.modelo == _MODELO_100 and any(
        item.ejercicio.resolve(world.envelope) == plan.year for item in world.work_income_none_statements
    )
    return (Statement(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION),) if stated else ()


def _rental_row(rental: RentalProperty, world: PersonaWorld) -> str:
    """The source identity of the profile row that holds ``rental``, found by its stated cadastral reference."""
    held = inmuebles_from_facts(record_to_path_values(load_profile_record(world)))
    keys = [item.clave for item in held if item.referencia_catastral == rental.referencia_catastral]
    if len(keys) != 1:
        raise PersonaMaterialisationError(f"{rental.id}: the profile holds {len(keys)} properties of its reference")
    return f"inmueble:{keys[0]}"


def _rental_refusal(rentals: Sequence[RentalProperty]) -> str | None:
    """The table's refusal of a pending total, which anexo C.1 cannot take without its origin years."""
    total = next((rental for rental in rentals if rental.pendiente_intereses_reparacion != Decimal(0)), None)
    if total is None:
        return None
    return (
        f"{total.id}: pendiente_intereses_reparacion states {total.pendiente_intereses_reparacion} as one total; "
        "anexo C.1 needs the pending amount stated per origin year, which this persona does not state"
    )


def rental_statements(persona: Persona, world: PersonaWorld, plan: PlannedRow) -> tuple[Statement, ...]:
    """The statement of no amount on each origin year's opening of each let property that states a pending carry.

    It follows the calculation that emits the property's row, so it belongs to the last phase.
    """
    rentals = [item for item in persona.rental_properties if item.pendiente_intereses_reparacion is not None]
    if plan.modelo != _MODELO_100 or not rentals:
        return ()
    phase = Phase.AFTER_RECALCULATION
    if (refusal := _rental_refusal(rentals)) is not None:
        return (Statement(StatementKind.RENTAL_CARRY, phase, refusal=refusal),)
    revision = world.operation.snapshot(
        plan.modelo, filing_year=plan.year, period=plan.period, grade=RegistryAuthorityGrade.CALCULATION
    ).revision
    openings = renta_inmueble_origin_columns(revision)[RentaInmuebleOriginPart.OPENING]
    try:
        rows = {rental.id: _rental_row(rental, world) for rental in rentals}
    except PersonaMaterialisationError as error:
        return (Statement(StatementKind.RENTAL_CARRY, phase, refusal=str(error)),)
    return tuple(
        Statement(StatementKind.RENTAL_CARRY, phase, target=str(binding.id), row=rows[rental.id])
        for rental in rentals
        for _back, binding in sorted(openings.items())
    )


def statements_for(materialised: MaterialisedPersona, plan: PlannedRow) -> tuple[Statement, ...]:
    """Every statement the table makes about ``plan``'s return, in the order it makes them.

    That is the planner's ``state_before_first_calculation`` (the carries, then the prior figures stated before the
    first calculation), the work inputs entered with the first calculation, the figures and the work-income statement
    that follow it, and last the rental carry stated on the calculated return.
    """
    world, persona = materialised.world, materialised.persona
    made = (
        *carry_statements(persona.prior_carries, world.envelope, plan),
        *prior_value_statements(world, plan),
        *work_input_statements(world, plan),
        *work_income_statements(world, plan),
        *rental_statements(persona, world, plan),
    )
    order = tuple(Phase)
    return (*sorted(made, key=lambda statement: order.index(statement.phase)),)
