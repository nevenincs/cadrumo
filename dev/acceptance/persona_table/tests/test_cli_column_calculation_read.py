"""After a statement, the CLI column reads the calculation the statement's edit made instead of calculating again.

The table calculates replaying the head (``caller_context`` ``replay_head``, the request's default), which keeps every
statement the edits recorded. ``aeat app modelo work calculate`` names no caller context and sends ``explicit``, which
replaces them with the inputs on its command line, so after an applied statement the driver reads the revision that
statement's edit printed. The statements come from the persona catalogue through the CLI column's own builder; the
runner replaces the ``aeat`` process only, and every command line is parsed by the live command tree.
"""

from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import typer
from typer.core import TyperCommand, TyperGroup

from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateRequest,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.cli.command_operation_table import COMMAND_OPERATION_ROWS
from cadrumo.entrypoints.cli.tests.cli_runner import cadrumo_click_command
from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona, PersonaWorld
from cadrumo.entrypoints.tests.persona_prior_values import entries_on
from cadrumo.entrypoints.tests.persona_work_inputs import resolved_casillas, work_inputs_for

from .. import planner
from ..cli_column.driver import READ_BACK, Case, run_case, select_rows
from ..cli_column.hygiene import Redactor
from ..cli_column.intake import LineWriter
from ..cli_column.statements import plain_amount, statements_for
from ..cli_column.world_report import RowPlan, WorldReport
from ..planner import persona_under_horizon, plan_rows, registry_envelope
from ..rows import PlannedRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ACTOR = "operator:test"
_STATEMENT_DOORS = frozenset(
    {"attest-prior-carries", "attest-prior-value", "set-value", "attest-work-income", "attest-no-amount"}
)


def _typer_command(candidate: object) -> TyperGroup | TyperCommand:
    assert isinstance(candidate, TyperGroup | TyperCommand)
    return candidate


def _parsed(argv: Sequence[str]) -> tuple[str, dict[str, object]]:
    """The live leaf ``argv`` names and the parameters it reads from the words after its path."""
    command = _typer_command(cadrumo_click_command())
    ctx = typer.Context(command, info_name="aeat")
    words = list(argv)
    while isinstance(command, TyperGroup):
        child = _typer_command(command.get_command(ctx, words[0]))
        command, words, ctx = child, words[1:], typer.Context(child, info_name=child.name, parent=ctx)
    return command.name or "", dict(command.make_context(command.name or "", words, parent=ctx.parent).params)


def _row(persona_id: str, modelo: str, period: str) -> PlannedRow:
    """The planner's row of ``modelo`` ``period`` in the year before the registry horizon."""
    horizon = registry_envelope().horizon
    rows, _emitted = plan_rows(persona_id, horizon)
    return next(row for row in rows if (row.modelo, row.year, row.period) == (modelo, horizon - 1, period))


def _opaque(value: object) -> object:
    """The value as a plain object, which a test holder is cast from."""
    return value


def _materialised(persona_id: str, operation: object) -> MaterialisedPersona:
    """The persona and a plain holder of the world facts the statement builder reads; no profile is materialised."""
    persona = persona_under_horizon(persona_id, registry_envelope().horizon)
    world = SimpleNamespace(
        envelope=registry_envelope(),
        operation=operation,
        attested_prior_values=persona.attested_prior_values,
        work_inputs=persona.work_inputs,
        work_income_none_statements=persona.work_income_none_statements,
    )
    held = SimpleNamespace(persona=persona, world=cast(PersonaWorld, _opaque(world)))
    return cast(MaterialisedPersona, _opaque(held))


def _plan(persona_id: str, modelo: str, period: str) -> RowPlan:
    """The return as the world report carries it, with the statements the CLI column builds from the persona."""
    row = _row(persona_id, modelo, period)
    with bundled_indexed_authority().operation() as operation:
        made = statements_for(_materialised(persona_id, operation), row)
    return RowPlan(row.modelo, row.year, row.period, True, True, False, row.period, statements=made)


def _ok(**result: object) -> dict[str, object]:
    return {"status": "success", "result": result}


class _Runner:
    """Answer each command as the backend prints it; a statement applies and names the calculation its edit made."""

    def __init__(self, exports: Path) -> None:
        self.sent: list[tuple[str, ...]] = []
        self._exports = exports

    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object]:
        del authenticated
        command = tuple(args)
        self.sent.append(command)
        key = "export" if command[:3] == ("app", "modelo", "export") else command[3]
        if key == "create":
            return _ok(work_unit_id="wu-1")
        if key in _STATEMENT_DOORS:
            return _ok(applied=True, receipt_id="r", calculation_revision_id=f"rev-{len(self.sent)}")
        if key in {"calculate", READ_BACK}:
            revision = f"rev-{len(self.sent)}" if key == "calculate" else command[4]
            return _ok(calculation_revision_id=revision, casilla_values={"01": "1"})
        if key == "verify":
            return _ok(granted_verificado_completo=True, findings=[])
        if key == "export":
            Path(command[command.index("--output") + 1]).write_text("fichero", encoding="utf-8")
        return _ok()


def _drive(tmp_path: Path, plan: RowPlan) -> list[tuple[str, ...]]:
    report = WorldReport("p", plan.year + 1, "root", "id", "gen", "as-of", "full", _ACTOR, False, (plan,))
    runner = _Runner(tmp_path)
    writer = LineWriter(tmp_path / "cli.jsonl", Redactor(["synthetic-persona-passphrase"]))
    run_case(Case("t", report, runner, tmp_path, writer, "case.log", export_check=lambda *_: ""), select_rows(report))
    (line,) = [json.loads(text) for text in (tmp_path / "cli.jsonl").read_text(encoding="utf-8").splitlines()]
    assert (line["calculate"], line["verify"], line["file"]) == ("pass", "pass", "pass")
    assert line["workaround"] == "cli_calculate_drops_statements"
    return runner.sent


def _verb(command: tuple[str, ...]) -> str:
    return "export" if command[:3] == ("app", "modelo", "export") else command[3]


def _read_after_each_statement_run(sent: list[tuple[str, ...]]) -> None:
    """No ``calculate`` follows an applied statement, and each read names the revision the last statement printed."""
    printed: str | None = None
    for index, command in enumerate(sent, start=1):
        verb = _verb(command)
        if verb in _STATEMENT_DOORS:
            printed = f"rev-{index}"
        elif verb == "calculate":
            assert printed is None, f"calculate after a statement drops it: {command}"
        elif verb == READ_BACK:
            assert command[4] == printed
            printed = None
        _parsed(command)


def test_the_table_replays_the_head_while_the_live_calculate_door_names_no_caller_context() -> None:
    called = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(planner.build_calculation_request)))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == ModeloWorkCalculateRequest.__name__
    ]
    assert called
    assert all(keyword.arg != "caller_context" for call in called for keyword in call.keywords)
    assert ModeloWorkCalculateRequest(work_unit_id="c" * 64, actor=_ACTOR).caller_context is (
        ModeloWorkCalculateCallerContext.REPLAY_HEAD
    )
    name, parameters = _parsed(["app", "modelo", "work", "calculate", "c" * 64, "--by", _ACTOR])
    assert name == "calculate"
    assert not [parameter for parameter in parameters if "caller" in parameter or "replay" in parameter]


def test_the_read_door_is_a_live_leaf_that_reads_one_revision_by_its_id() -> None:
    name, parameters = _parsed(["app", "modelo", "work", READ_BACK, "rev-1"])

    assert name == READ_BACK
    assert parameters["calculation_revision_id"] == "rev-1"
    read = ("app", "modelo", "work", READ_BACK)
    assert "modelo.work.revision" in {operation for path, operation in COMMAND_OPERATION_ROWS if path == read}


def test_a_figure_stated_before_and_after_the_calculation_is_read_back_both_times(tmp_path: Path) -> None:
    plan = _plan("autonomo-electricista", "130", "1T")
    persona = persona_under_horizon("autonomo-electricista", registry_envelope().horizon)
    (entry,) = entries_on(
        persona.attested_prior_values, registry_envelope(), modelo="130", filing_year=plan.year, period="1T"
    )

    sent = _drive(tmp_path, plan)

    stated = [
        "attest-prior-value",
        "--yes",
        "--output-language",
        "en",
        "wu-1",
        entry.binding,
        plain_amount(entry.value),
    ]
    assert [_verb(command) for command in sent] == [
        "create",
        "attest-prior-value",
        READ_BACK,
        "attest-prior-value",
        READ_BACK,
        "verify",
        "export",
        "file",
    ]
    assert list(sent[1][3:]) == list(sent[3][3:]) == stated
    assert sent[5][4] == sent[4][4] == "rev-4"
    _read_after_each_statement_run(sent)


def test_the_typed_values_and_the_figures_after_them_are_read_back_never_recalculated(tmp_path: Path) -> None:
    plan = _plan("sociedad-limitada", "200", "0A")
    persona = persona_under_horizon("sociedad-limitada", registry_envelope().horizon)
    entry = work_inputs_for(persona.work_inputs, registry_envelope(), modelo="200", year=plan.year, period="0A")
    assert entry is not None
    with bundled_indexed_authority().operation() as operation:
        revision = operation.revision_for_context("200", filing_year=plan.year, period="0A")
        typed = resolved_casillas(revision, entry, where="200")

    sent = _drive(tmp_path, plan)

    verbs = [_verb(command) for command in sent]
    assert verbs[: len(typed) + 2] == ["create", *["set-value"] * len(typed), READ_BACK]
    assert [command[-2] for command in sent[1 : len(typed) + 1]] == [casilla for casilla, _ in typed]
    assert "calculate" not in verbs
    assert verbs[-3:] == ["verify", "export", "file"]
    _read_after_each_statement_run(sent)


def test_the_carries_and_the_work_income_statement_are_read_back_never_recalculated(tmp_path: Path) -> None:
    plan = _plan("asalariada-familia", "100", "0A")
    persona = persona_under_horizon("asalariada-familia", registry_envelope().horizon)
    families = [item.family for item in persona.prior_carries if item.year.resolve(registry_envelope()) == plan.year]

    sent = _drive(tmp_path, plan)

    assert [_verb(command) for command in sent] == [
        "create",
        "attest-prior-carries",
        READ_BACK,
        "attest-work-income",
        READ_BACK,
        "verify",
        "export",
        "file",
    ]
    _name, parameters = _parsed(sent[1])
    named = parameters["family"]
    assert isinstance(named, list | tuple)
    assert [getattr(family, "value", family) for family in named] == list(dict.fromkeys(families))
    _read_after_each_statement_run(sent)
