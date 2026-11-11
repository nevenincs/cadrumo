"""A persona's stated pending Modelo 100 carries reach the declaration through the operations the refusal's door names.

With no earlier return held, as for the return of the support floor, a Modelo
100 cannot read the negative general bases pending from the four previous
ejercicios and refuses to calculate. The persona's ``[[prior_carries]]``
statement, made between create and calculate, answers them; without it the
refusal stands. Real behaviour throughout: a materialised persona, the
production registered operations and the bundled authority.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from decimal import Decimal

import pytest

from ...application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculatePublicResultV3,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import restore_scalar
from ...tests.personas import PRIOR_CARRY_BOXES, Persona, PriorCarries, YearToken
from .persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    materialised_persona,
    run_operation,
    settle_operation,
)
from .persona_prior_carries import attest_prior_carries

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PERSONA = "arrendador-jubilado"
_REFUSAL = "REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED"


@pytest.fixture(scope="module")
def renta_world(tmp_path_factory: pytest.TempPathFactory) -> Iterator[MaterialisedPersona]:
    """The persona's profile without the history scope, so no earlier Modelo 100 is held for any year."""
    with materialised_persona(_PERSONA, tmp_path_factory.mktemp("persona"), ReplayScope.FULL) as materialised:
        yield materialised


def _created(world: PersonaWorld, year: int) -> str:
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo="100",
            period=PublicPeriod(filing_year=year, code="0A"),
            actor=PERSONA_ACTOR,
        ),
    )
    assert isinstance(created, ModeloWorkCreateProjection)
    assert isinstance(created.outcome, ModeloWorkCreateSuccess), created.outcome
    return created.outcome.unit.work_unit_id


def _calculated(world: PersonaWorld, work_unit_id: str) -> dict[str, object]:
    calculated = run_operation(
        world,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        ModeloWorkCalculateRequest(work_unit_id=work_unit_id, actor=PERSONA_ACTOR),
        ModeloWorkCalculatePublicResultV3,
        subject=work_unit_id,
    )
    return {str(item.key): restore_scalar(item.value) for item in calculated.calculation.casilla_values}


def _stating(persona: Persona, token: str, pending: tuple[tuple[str, Decimal], ...] = ()) -> Persona:
    statement = PriorCarries(year=YearToken.parse(token, where="test"), pending=pending)
    return dataclasses.replace(persona, prior_carries=(statement,))


def test_the_floor_year_return_refuses_until_the_persona_states_nothing_is_pending(
    renta_world: MaterialisedPersona,
) -> None:
    world = renta_world.world
    floor = world.envelope.floor
    persona = _stating(renta_world.persona, "floor")
    work_unit_id = _created(world, floor)

    with pytest.raises(PersonaMaterialisationError, match=_REFUSAL):
        _calculated(world, work_unit_id)

    answered = attest_prior_carries(persona, world, work_unit_id, floor)
    assert len(answered) >= len(PRIOR_CARRY_BOXES)
    values = _calculated(world, work_unit_id)
    assert all(Decimal(str(values[box])) == 0 for box in PRIOR_CARRY_BOXES)
    # Every carry is answered, so a second statement has nothing left to do.
    assert attest_prior_carries(persona, world, work_unit_id, floor) == ()


def test_a_persona_that_states_nothing_for_the_year_leaves_the_refusal_standing(
    renta_world: MaterialisedPersona,
) -> None:
    world = renta_world.world
    year = world.envelope.floor + 1
    work_unit_id = _created(world, year)

    assert attest_prior_carries(_stating(renta_world.persona, "floor"), world, work_unit_id, year) == ()
    with pytest.raises(PersonaMaterialisationError, match=_REFUSAL):
        _calculated(world, work_unit_id)


def test_a_stated_pending_amount_feeds_its_box_and_the_boxes_left_out_hold_nothing(
    renta_world: MaterialisedPersona,
) -> None:
    world = renta_world.world
    year = world.envelope.floor + 2
    stated_box, *other_boxes = PRIOR_CARRY_BOXES
    persona = _stating(renta_world.persona, "floor+2", ((stated_box, Decimal("300.00")),))
    work_unit_id = _created(world, year)

    assert attest_prior_carries(persona, world, work_unit_id, year)
    values = _calculated(world, work_unit_id)
    assert Decimal(str(values[stated_box])) == Decimal("300.00")
    assert all(Decimal(str(values[box])) == 0 for box in other_boxes)


def test_the_catalogue_statement_answers_the_return_the_persona_owes(renta_world: MaterialisedPersona) -> None:
    persona, world = renta_world.persona, renta_world.world
    (statement,) = persona.prior_carries
    year = statement.year.resolve(world.envelope)
    work_unit_id = _created(world, year)

    assert attest_prior_carries(persona, world, work_unit_id, year)
    assert _calculated(world, work_unit_id)
