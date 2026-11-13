"""The statements the CLI column makes are the facts the persona catalogue gives, in the order the planner states them.

The persona data is read by the catalogue's own reader and the registry edition is the bundled published authority;
only the world that carries the persona's facts into the builder is a plain holder, since materialising a profile
is what these tests do not need.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona, PersonaWorld

from .. import planner
from ..cli_column import statements as builder
from ..cli_column.statements import (
    carry_amount,
    carry_statements,
    plain_amount,
    prior_value_statements,
    rental_statements,
    statements_for,
    work_input_statements,
)
from ..cli_column.world_report import Phase, Statement, StatementKind
from ..planner import persona_under_horizon, plan_rows, registry_envelope
from ..rows import PlannedRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _row(persona_id: str, modelo: str, year_offset: int, period: str) -> PlannedRow:
    """The planner's row of ``modelo`` ``period`` in the year ``year_offset`` from the registry horizon."""
    horizon = registry_envelope().horizon
    rows, _emitted = plan_rows(persona_id, horizon)
    year = horizon + year_offset
    return next(row for row in rows if (row.modelo, row.year, row.period) == (modelo, year, period))


def _opaque(value: object) -> object:
    """The value as a plain object, which a test holder is cast from."""
    return value


def _world(persona_id: str, operation: object) -> PersonaWorld:
    persona = persona_under_horizon(persona_id, registry_envelope().horizon)
    held = SimpleNamespace(
        envelope=registry_envelope(),
        operation=operation,
        attested_prior_values=persona.attested_prior_values,
        work_inputs=persona.work_inputs,
        work_income_none_statements=persona.work_income_none_statements,
    )
    return cast(PersonaWorld, _opaque(held))


def _materialised(persona_id: str, operation: object) -> MaterialisedPersona:
    persona = persona_under_horizon(persona_id, registry_envelope().horizon)
    held = SimpleNamespace(persona=persona, world=_world(persona_id, operation))
    return cast(MaterialisedPersona, _opaque(held))


def _summary(made: tuple[Statement, ...]) -> list[tuple[str, str, str, str]]:
    return [(item.kind.value, item.phase.value, item.target, item.value) for item in made]


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("21000.00"), "21000"),
        (Decimal("0.50"), "0.5"),
        (Decimal("1E+3"), "1000"),
        (Decimal("0E-2"), "0"),
        (Decimal("-12.50"), "-12.5"),
    ],
)
def test_an_amount_is_plain_decimal_text_without_an_exponent_or_trailing_zeros(amount: Decimal, text: str) -> None:
    assert plain_amount(amount) == text


def test_a_pending_amount_is_said_by_its_box_when_positive_and_with_at_most_two_decimals() -> None:
    assert carry_amount("1380", Decimal("1234.50")) == ("1380", "1234.5")
    assert carry_amount("1380", Decimal("0.00")) is None
    assert "positive amount of at most two decimals" in str(carry_amount("1380", Decimal("-5")))
    assert "box 1382 states 0.001" in str(carry_amount("1382", Decimal("0.001")))


def test_the_pending_carries_of_a_year_travel_as_one_statement_of_every_family_the_persona_names() -> None:
    envelope = registry_envelope()
    persona = persona_under_horizon("asalariada-familia", envelope.horizon)
    families = (
        "renta_negative_general_bases_pending",
        "renta_negative_savings_capital_income_pending",
        "renta_negative_savings_gains_losses_pending",
    )

    for offset in (-1, -2):
        made = carry_statements(persona.prior_carries, envelope, _row("asalariada-familia", "100", offset, "0A"))

        assert made == (Statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, families=families),)


def test_no_carry_is_stated_for_a_return_that_is_not_a_modelo_100_or_for_a_year_the_persona_is_silent_on() -> None:
    envelope = registry_envelope()
    persona = persona_under_horizon("autonomo-electricista", envelope.horizon)

    assert carry_statements(persona.prior_carries, envelope, _row("autonomo-electricista", "130", -1, "1T")) == ()
    assert carry_statements((), envelope, _row("autonomo-electricista", "100", -1, "0A")) == ()


def test_a_figure_attested_for_a_return_is_stated_before_its_calculation_and_again_after_it() -> None:
    with bundled_indexed_authority().operation() as operation:
        world = _world("autonomo-electricista", operation)
        first = prior_value_statements(world, _row("autonomo-electricista", "130", -1, "1T"))
        silent = prior_value_statements(world, _row("autonomo-electricista", "303", -1, "1T"))

    binding = "irpf.previous_year_economic_activity_net_income"
    assert _summary(first) == [
        ("prior_value", "before_evidence", binding, "21000"),
        ("prior_value", "after_calculation", binding, "21000"),
    ]
    assert silent == ()


def test_the_values_the_operator_types_resolve_to_their_casillas_and_the_figures_wait_for_the_calculation() -> None:
    plan = _row("sociedad-limitada", "200", -1, "0A")
    with bundled_indexed_authority().operation() as operation:
        world = _world("sociedad-limitada", operation)
        typed = work_input_statements(world, plan)
        figures = prior_value_statements(world, plan)

    assert [(item.phase, item.value) for item in typed] == [
        (Phase.AT_CALCULATION, "25400"),
        (Phase.AT_CALCULATION, "16300"),
    ]
    assert [item.target for item in typed] == ["DP200012:00501", "DP200014:00547"]
    assert {item.phase for item in figures} == {Phase.AFTER_CALCULATION}
    assert [item.value for item in figures] == ["16300", "0", "0"]


def test_the_work_income_statement_follows_the_calculation_of_the_ejercicio_it_is_made_for() -> None:
    with bundled_indexed_authority().operation() as operation:
        made = statements_for(
            _materialised("asalariada-familia", operation), _row("asalariada-familia", "100", -1, "0A")
        )
        elsewhere = statements_for(
            _materialised("autonomo-electricista", operation), _row("autonomo-electricista", "100", -1, "0A")
        )

    assert [(item.kind, item.phase) for item in made] == [
        (StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE),
        (StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION),
    ]
    assert StatementKind.WORK_INCOME_NONE not in {item.kind for item in elsewhere}


def test_a_pending_total_the_table_refuses_is_a_refusal_not_a_door_and_a_persona_without_one_states_nothing() -> None:
    plan = _row("arrendador-jubilado", "100", -1, "0A")
    persona = persona_under_horizon("arrendador-jubilado", registry_envelope().horizon)
    stated = [
        dataclasses.replace(rental, pendiente_intereses_reparacion=Decimal("5")) for rental in persona.rental_properties
    ]
    with_total = dataclasses.replace(persona, rental_properties=tuple(stated))
    silent = dataclasses.replace(
        persona,
        rental_properties=tuple(
            dataclasses.replace(rental, pendiente_intereses_reparacion=None) for rental in persona.rental_properties
        ),
    )
    with bundled_indexed_authority().operation() as operation:
        world = _world("arrendador-jubilado", operation)
        refused = rental_statements(with_total, world, plan)
        none_stated = rental_statements(silent, world, plan)

    (statement,) = refused
    assert (statement.kind, statement.phase) == (StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION)
    assert statement.refusal is not None
    assert "states 5 as one total" in statement.refusal
    assert statement.gap is None
    assert none_stated == ()


def _call_order(function: Callable[..., object], names: set[str]) -> list[str]:
    """The names among ``names`` that the function's source calls, in source order."""
    tree = ast.parse(inspect.getsource(function))
    calls = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.Call)), key=lambda node: (node.lineno, node.col_offset)
    )
    called = (call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "") for call in calls)
    return [name for name in called if name in names]


def test_the_phases_follow_the_planner_which_states_the_carries_first_and_requests_after_the_statements() -> None:
    assert _call_order(
        planner.state_before_first_calculation, {"attest_prior_carries", "attest_before_first_calculation"}
    ) == ["attest_prior_carries", "attest_before_first_calculation"]
    assert _call_order(planner.prepare_return, {"state_before_first_calculation", "build_calculation_request"}) == [
        "state_before_first_calculation",
        "build_calculation_request",
    ]
    assert _call_order(
        builder.statements_for,
        {
            "carry_statements",
            "prior_value_statements",
            "work_input_statements",
            "work_income_statements",
            "rental_statements",
        },
    ) == [
        "carry_statements",
        "prior_value_statements",
        "work_input_statements",
        "work_income_statements",
        "rental_statements",
    ]
    assert list(Phase) == [
        Phase.BEFORE_EVIDENCE,
        Phase.AT_CALCULATION,
        Phase.AFTER_CALCULATION,
        Phase.AFTER_RECALCULATION,
    ]
