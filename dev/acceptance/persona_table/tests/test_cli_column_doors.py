"""Each statement the table makes has a command in the live command tree that submits the same registered operations.

The command tree here is the Typer application the ``aeat`` executable runs, loaded and walked by Click, and the
arguments are parsed by the command's own parameters, so a renamed command, a dropped option or a changed operand
fails these tests. Nothing is sent: the commands are parsed, not run.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
import typer
from typer.core import TyperCommand, TyperGroup

from cadrumo.application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.workbench_operations import (
    MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID,
    MODELO_WORK_FORM_OPERATION_DEFINITION_ID,
)
from cadrumo.entrypoints.cli.command_operation_table import COMMAND_OPERATION_ROWS
from cadrumo.entrypoints.cli.tests.cli_runner import cadrumo_click_command
from cadrumo.entrypoints.tests.persona_materialisation import PERSONA_PROFILE_CREDENTIAL

from ..cli_column.doors import (
    DOORS,
    EFFECT_OPERATION,
    FORM_OPERATION,
    PREFLIGHT_OPERATION,
    TABLE_OPERATIONS,
    statement_args,
    statement_gap,
)
from ..cli_column.world_report import Phase, Statement, StatementKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_UNIT = "c" * 64
_FAMILY = "renta_negative_general_bases_pending"


def _typer_command(candidate: object) -> TyperGroup | TyperCommand:
    assert isinstance(candidate, TyperGroup | TyperCommand)
    return candidate


def _leaf(argv: Sequence[str], *, parse: bool) -> tuple[TyperGroup | TyperCommand, dict[str, object], list[str]]:
    """The leaf ``argv`` names in the live tree, the parameters it reads from the words after its path, the words left.

    The words after the path are parsed by the leaf's own parameters only when ``parse``.
    """
    command = _typer_command(cadrumo_click_command())
    ctx = typer.Context(command, info_name="aeat")
    words = list(argv)
    while isinstance(command, TyperGroup):
        child = _typer_command(command.get_command(ctx, words[0]))
        command, words, ctx = child, words[1:], typer.Context(child, info_name=child.name, parent=ctx)
    if not parse:
        return command, {}, words
    return command, dict(command.make_context(command.name or "", words, parent=ctx.parent).params), []


def _parsed(statement: Statement) -> dict[str, object]:
    """The parameters the live command reads from the arguments that make ``statement``."""
    return _leaf(statement_args(statement, _UNIT), parse=True)[1]


def _one_of_each() -> dict[StatementKind, Statement]:
    return {
        StatementKind.PRIOR_CARRIES: Statement(
            StatementKind.PRIOR_CARRIES,
            Phase.BEFORE_EVIDENCE,
            families=(_FAMILY, "renta_negative_savings_capital_income_pending"),
            amounts=(("1380", "10.5"),),
        ),
        StatementKind.PRIOR_VALUE: Statement(
            StatementKind.PRIOR_VALUE, Phase.BEFORE_EVIDENCE, target="irpf.previous_year", value="21000"
        ),
        StatementKind.WORK_INPUT: Statement(
            StatementKind.WORK_INPUT, Phase.AT_CALCULATION, target="00501", value="25400.5"
        ),
        StatementKind.WORK_INCOME_NONE: Statement(StatementKind.WORK_INCOME_NONE, Phase.AFTER_CALCULATION),
        StatementKind.RENTAL_CARRY: Statement(
            StatementKind.RENTAL_CARRY, Phase.AFTER_RECALCULATION, target="irpf.opening", row="inmueble:k1"
        ),
    }


def test_every_kind_of_statement_has_a_door_and_every_door_a_kind() -> None:
    assert set(DOORS) == set(StatementKind) == set(TABLE_OPERATIONS)


@pytest.mark.parametrize("kind", list(StatementKind))
def test_a_door_is_a_leaf_of_the_live_command_tree(kind: StatementKind) -> None:
    command, _none, words = _leaf(DOORS[kind].path, parse=False)

    assert not isinstance(command, TyperGroup)
    assert words == []
    assert command.name == DOORS[kind].path[-1]


@pytest.mark.parametrize("kind", list(StatementKind))
def test_a_door_submits_every_operation_the_table_runs_to_make_the_statement(kind: StatementKind) -> None:
    submitted = {operation for path, operation in COMMAND_OPERATION_ROWS if path == DOORS[kind].path}

    assert set(TABLE_OPERATIONS[kind]) <= submitted


def test_the_operation_ids_the_doors_name_are_the_ones_the_table_submits() -> None:
    assert FORM_OPERATION == MODELO_WORK_FORM_OPERATION_DEFINITION_ID
    assert PREFLIGHT_OPERATION == MODELO_EDIT_PREFLIGHT_OPERATION_DEFINITION_ID
    assert EFFECT_OPERATION == MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID


def test_prior_carries_name_each_family_and_each_amount_by_its_box() -> None:
    parsed = _parsed(_one_of_each()[StatementKind.PRIOR_CARRIES])

    assert parsed["work_unit_id"] == _UNIT
    families = parsed["family"]
    assert isinstance(families, list | tuple)
    assert [getattr(family, "value", family) for family in families] == [
        _FAMILY,
        "renta_negative_savings_capital_income_pending",
    ]
    amounts = parsed["amount"]
    assert isinstance(amounts, list | tuple)
    assert list(amounts) == ["1380=10.5"]
    assert parsed["confirmed"] is True


def test_a_prior_value_and_a_work_input_name_the_work_unit_the_target_and_the_value_in_english() -> None:
    prior = _parsed(_one_of_each()[StatementKind.PRIOR_VALUE])
    typed = _parsed(_one_of_each()[StatementKind.WORK_INPUT])

    assert (prior["work_unit_id"], prior["binding_id"], prior["value"]) == (_UNIT, "irpf.previous_year", "21000")
    assert (typed["work_unit_id"], typed["casilla_id"], typed["value"]) == (_UNIT, "00501", "25400.5")
    assert str(prior["output_language"]) == str(typed["output_language"]) == "en"
    assert prior["confirmed"] is typed["confirmed"] is True


def test_the_work_income_and_rental_statements_name_the_work_unit_and_the_row() -> None:
    income = _parsed(_one_of_each()[StatementKind.WORK_INCOME_NONE])
    rental = _parsed(_one_of_each()[StatementKind.RENTAL_CARRY])

    assert income["work_unit_id"] == _UNIT
    assert (rental["work_unit_id"], rental["binding_id"], rental["row_identity"]) == (
        _UNIT,
        "irpf.opening",
        "inmueble:k1",
    )


def test_a_negative_value_follows_the_end_of_options_and_is_read_as_a_value() -> None:
    negative = Statement(StatementKind.WORK_INPUT, Phase.AT_CALCULATION, target="00501", value="-12.5")

    args = statement_args(negative, _UNIT)
    parsed = _parsed(negative)

    assert args[-4:] == ["--", _UNIT, "00501", "-12.5"]
    assert (parsed["work_unit_id"], parsed["casilla_id"], parsed["value"]) == (_UNIT, "00501", "-12.5")


def test_the_arguments_are_in_the_live_tree_and_carry_no_secret() -> None:
    for kind, statement in _one_of_each().items():
        args = statement_args(statement, _UNIT)
        command, _parsed_args, _rest = _leaf(args, parse=True)

        assert args[: len(DOORS[kind].path)] == list(DOORS[kind].path)
        assert PERSONA_PROFILE_CREDENTIAL not in " ".join(args)
        assert not any("secret" in (parameter.name or "") for parameter in command.params)


def test_a_statement_without_a_door_or_a_way_to_say_it_is_named_by_its_operation() -> None:
    said = _one_of_each()[StatementKind.PRIOR_VALUE]
    unsayable = Statement(StatementKind.PRIOR_CARRIES, Phase.BEFORE_EVIDENCE, gap="box 1380 states -5")

    assert statement_gap((said,)) is None
    assert statement_gap((said,), doors={}) == "no CLI door for modelo.edit.apply (prior_value)"
    assert statement_gap((said, unsayable)) == "no CLI door for modelo.edit.apply (prior_carries: box 1380 states -5)"
