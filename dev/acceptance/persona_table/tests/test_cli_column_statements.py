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

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona, PersonaWorld
from cadrumo.entrypoints.tests.persona_prior_values import entries_on
from cadrumo.tests.personas import AttestedPriorValue, YearToken

from .. import planner
from ..cli_column import statements as builder
from ..cli_column.statements import (
    carry_amount,
    carry_statements,
    declared_entries,
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


def _world(persona_id: str, operation: object, attested: tuple[AttestedPriorValue, ...] | None = None) -> PersonaWorld:
    persona = persona_under_horizon(persona_id, registry_envelope().horizon)
    held = SimpleNamespace(
        envelope=registry_envelope(),
        operation=operation,
        attested_prior_values=persona.attested_prior_values if attested is None else attested,
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

    assert {item.phase for item in typed} == {Phase.AT_CALCULATION}
    # the persona states nine roles: the two liquidacion lines, then the cuenta de perdidas y ganancias of pages 7 and 8
    # (cifra de negocios and prestaciones 30800, otros gastos, servicios exteriores and servicios exteriores resto
    # -5400, resultado de explotacion and resultado antes de impuestos 25400), each typed at its page-qualified casilla
    assert {item.target: item.value for item in typed} == {
        "DP200012:00501": "25400",
        "DP200014:00547": "16300",
        "DP200007:00255": "30800",
        "DP200007:00257": "30800",
        "DP200007:00279": "-5400",
        "DP200007:00280": "-5400",
        "DP200007:00254": "-5400",
        "DP200007:00296": "25400",
        "DP200008:00325": "25400",
    }
    assert len(typed) == 9
    assert {item.phase for item in figures} == {Phase.AFTER_CALCULATION}
    envelope = registry_envelope()
    persona = persona_under_horizon("sociedad-limitada", envelope.horizon)
    with bundled_indexed_authority().operation() as operation:
        declared = revision_bindings_by_id(operation.revision_for_context("200", filing_year=plan.year, period="0A"))
    stated = [
        entry
        for entry in entries_on(
            persona.attested_prior_values, envelope, modelo="200", filing_year=plan.year, period="0A"
        )
        if entry.binding in declared
    ]
    assert stated
    assert [item.target for item in figures] == [entry.binding for entry in stated]
    assert [item.value for item in figures] == [plain_amount(entry.value) for entry in stated]


def _incn_entry() -> AttestedPriorValue:
    """The sociedad-limitada attestation that states ``where_declared``, which only some editions declare."""
    persona = persona_under_horizon("sociedad-limitada", registry_envelope().horizon)
    (entry,) = (item for item in persona.attested_prior_values if item.where_declared)
    return entry


def _declaring_and_lacking(operation: PinnedAuthorityOperation, entry: AttestedPriorValue) -> tuple[int, int]:
    """A supported filing year whose edition declares the entry's binding, and one whose edition lacks it."""
    envelope = registry_envelope()
    declares = {
        year: entry.binding
        in revision_bindings_by_id(operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period))
        for year in range(envelope.floor, envelope.horizon + 1)
    }
    return (
        max(year for year, declared in declares.items() if declared),
        max(year for year, declared in declares.items() if not declared),
    )


def _stated_in(operation: PinnedAuthorityOperation, entry: AttestedPriorValue, year: int) -> tuple[Statement, ...]:
    """The prior-value statements of the Modelo 200 return of ``year`` for a persona that states only ``entry``."""
    envelope = registry_envelope()
    stated = dataclasses.replace(entry, year=YearToken(anchor="horizon", offset=year - envelope.horizon))
    plan = dataclasses.replace(_row("sociedad-limitada", "200", -1, "0A"), year=year)
    return prior_value_statements(_world("sociedad-limitada", operation, (stated,)), plan)


def test_an_entry_that_states_where_declared_is_dropped_for_an_edition_lacking_its_binding_and_kept_otherwise() -> None:
    entry = _incn_entry()
    with bundled_indexed_authority().operation() as operation:
        declaring, lacking = _declaring_and_lacking(operation, entry)
        kept = _stated_in(operation, entry, declaring)
        dropped = _stated_in(operation, entry, lacking)

    assert {item.target for item in kept} == {entry.binding}
    assert {item.value for item in kept} == {plain_amount(entry.value)}
    assert dropped == ()


def test_an_entry_without_the_flag_is_never_dropped_even_for_an_edition_lacking_its_binding() -> None:
    strict = dataclasses.replace(_incn_entry(), where_declared=False)
    with bundled_indexed_authority().operation() as operation:
        declaring, lacking = _declaring_and_lacking(operation, strict)
        kept = [_stated_in(operation, strict, year) for year in (declaring, lacking)]

    assert all({item.target for item in made} == {strict.binding} for made in kept)


def test_a_return_the_registry_selects_no_edition_for_keeps_every_entry_for_its_own_refusal() -> None:
    entry = _incn_entry()
    plan = dataclasses.replace(_row("sociedad-limitada", "200", -1, "0A"), modelo="999")
    with bundled_indexed_authority().operation() as operation:
        world = _world("sociedad-limitada", operation, (entry,))
        assert declared_entries(world, plan, (entry,)) == (entry,)


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
