"""Drive each return the persona table reports for a persona through the Modelo workbench, over the persona's profile.

The persona is replayed into its registered profile by the persona materialisation support at every horizon the
table reports one of its returns at (:mod:`.plan`). Each return is created, then opened in the production workbench
(:mod:`cadrumo.entrypoints.tui.modelo.workbench.tests.workbench_driver`), and the pilot presses the key the
workbench names for each next step the form serves, as long as it serves an operation step (calculate, check,
export, record the filing); a step that asks the filer to fill in or confirm a value, a refusal, or no further step
ends the return. What the persona's operator states outside those keys (the values entered before the first
calculation, the prior carries and figures it attests, the statements a calculation offers) is submitted through
the same registered operations between the key presses, as the persona table does. A return the table holds not owed
is driven through calculate only, as the table stops it: its check, export and record are not pressed.

Each row is compared with the table's row for the return (:mod:`.causes`) and appended to the intake
(:mod:`.intake`) as soon as it is known.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.application.modelo.work_create_operation import (
    MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
    ModeloWorkCreateProjection,
    ModeloWorkCreateRequest,
    ModeloWorkCreateSuccess,
)
from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.core.config import override_settings
from cadrumo.core.logging import get_logger
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.modelos.verification_report import VerificationCompletenessStatus
from cadrumo.entrypoints.tests.persona_materialisation import (
    PERSONA_ACTOR,
    MaterialisedPersona,
    PersonaMaterialisationError,
    PersonaWorld,
    ReplayScope,
    attest_before_first_calculation,
    enter_return_work_inputs,
    filing_key,
    materialised_persona,
    public_result,
    settle_operation,
    state_after_calculation,
)
from cadrumo.entrypoints.tests.persona_prior_carries import attest_prior_carries
from cadrumo.entrypoints.tests.persona_rental_carries import attest_pending_rental_carries
from cadrumo.entrypoints.tui.modelo.workbench.tests.workbench_driver import (
    DialogAnswers,
    ShownOutcome,
    WorkbenchDriver,
    open_workbench,
)
from cadrumo.tests.personas import Persona, PersonaCatalogueError, read_persona

from ..persona_table.frontend import DIFFERS, NOT_REACHED
from ..persona_table.rows import PlannedRow, TableRow
from .causes import CRASH_CAUSE, export_unavailable_note, outcome, row_cause, unreported_cause
from .intake import ERROR, INCOMPLETE, NOT_OWED, PASSED, REFUSED, PilotRow, write_rows
from .plan import pilot_envelope, pilot_plan, table_rows_path

_CALCULATE: Final = frozenset({ModeloFormNextAction.CALCULATE, ModeloFormNextAction.RECALCULATE})
_EXPORT: Final = frozenset({ModeloFormNextAction.EXPORT, ModeloFormNextAction.EXPORT_AGAIN})
_STAGE_OF_ACTION: Final = {
    ModeloFormNextAction.CALCULATE: "calculate",
    ModeloFormNextAction.RECALCULATE: "calculate",
    ModeloFormNextAction.VERIFY: "verify",
    ModeloFormNextAction.EXPORT: "export",
    ModeloFormNextAction.EXPORT_AGAIN: "export",
    ModeloFormNextAction.RECORD_AFTER_FILE: "file",
}
"""The operation steps the pilot can take, by the row stage each settles."""
_SETTLED = re.compile(r"^(?P<definition>\S+) settled (?P<condition>\S+) \((?P<code>[^)]*)\)")
_REASON_LIMIT: Final = 600


@dataclass(frozen=True, slots=True)
class ReportedRow:
    """One reported return: the table's row for it, the TUI's row, and how the table counts the TUI row."""

    table: TableRow
    row: PilotRow
    outcome: str


@dataclass(frozen=True, slots=True)
class PersonaRun:
    """The persona-level line and every reported return."""

    loaded: PilotRow
    reported: tuple[ReportedRow, ...]


def replay_scope(persona: Persona) -> ReplayScope:
    """The records scope when the persona holds a return history, else the full ledger, as the persona table takes."""
    if persona.filed_returns or persona.calculated_returns or persona.local_observations or persona.aeat_filings:
        return ReplayScope.RECORDS
    return ReplayScope.FULL


# -- what the persona's operator states between the key presses -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Statements:
    """What the persona's operator states on the return between the workbench's key presses."""

    after_calculate: Callable[[ModeloWorkCalculatePublicResultV3], bool]
    """Make the statements the calculation offers; whether the return must be calculated again to read them."""
    after_settled_calculation: Callable[[], bool]
    """Make the statements that need a settled calculation; whether the return must be calculated again."""


def _statements(materialised: MaterialisedPersona, plan: PlannedRow, work_unit_id: str) -> _Statements:
    world = materialised.world

    def after_settled_calculation() -> bool:
        return plan.modelo == "100" and attest_pending_rental_carries(
            materialised.persona, world, work_unit_id, plan.year
        )

    return _Statements(
        after_calculate=lambda calculated: state_after_calculation(world, calculated),
        after_settled_calculation=after_settled_calculation,
    )


# -- one return -------------------------------------------------------------------------------------------------------


def _settled_stage(shown: ShownOutcome) -> str:
    condition = shown.condition
    if condition is OperationTerminalCondition.SUCCEEDED:
        return PASSED
    if condition is OperationTerminalCondition.REFUSED:
        return REFUSED
    return ERROR


async def _press_calculate(
    driver: WorkbenchDriver, statements: _Statements, action: ModeloFormNextAction, row: PilotRow
) -> ModeloWorkCalculatePublicResultV3 | None:
    """Press the key for ``action``; the calculation the workbench settled, or ``None`` with the reason in ``row``."""
    shown = await driver.press_for(action)
    row.calculate = _settled_stage(shown)
    if not shown.submitted:
        row.calculate = ERROR
        row.reasons.append(f"calculate: the workbench submitted nothing: {shown.notice}")
        return None
    if row.calculate != PASSED or shown.terminal is None:
        row.refusal_code = shown.code
        row.reasons.append(f"calculate: {shown.code} {shown.refusal or shown.notice}")
        return None
    calculated = await asyncio.to_thread(public_result, driver.world, shown.terminal)
    if not isinstance(calculated, ModeloWorkCalculatePublicResultV3):
        row.calculate = ERROR
        row.reasons.append(f"calculate: published {type(calculated).__name__}")
        return None
    return calculated


async def _calculate_round(
    driver: WorkbenchDriver, statements: _Statements, action: ModeloFormNextAction, row: PilotRow
) -> bool:
    """Calculate, and once more when the persona then states what the calculation offers, as the table does."""
    calculated = await _press_calculate(driver, statements, action, row)
    if calculated is None:
        return False
    if await asyncio.to_thread(statements.after_calculate, calculated):
        return await _press_calculate(driver, statements, ModeloFormNextAction.RECALCULATE, row) is not None
    return True


async def _calculate(
    driver: WorkbenchDriver, statements: _Statements, action: ModeloFormNextAction, row: PilotRow
) -> bool:
    """Take the served calculate step; again once the persona states what needs a settled calculation."""
    if not await _calculate_round(driver, statements, action, row):
        return False
    if await asyncio.to_thread(statements.after_settled_calculation):
        return await _calculate_round(driver, statements, ModeloFormNextAction.RECALCULATE, row)
    return True


def _verified(shown: ShownOutcome, row: PilotRow) -> bool:
    stage = _settled_stage(shown)
    if stage == PASSED and shown.verification is not VerificationCompletenessStatus.COMPLETE:
        stage = INCOMPLETE
    row.verify = stage if shown.submitted else ERROR
    if row.verify != PASSED:
        row.refusal_code = row.refusal_code or shown.code
        row.reasons.append(f"verify: {shown.verification} {shown.refusal or shown.notice}")
    return row.verify == PASSED


def _exported(shown: ShownOutcome, row: PilotRow) -> bool:
    if not shown.submitted:
        row.export = REFUSED
        withheld = f"the export dialog offers only {', '.join(shown.export_offered)}" if shown.export_offered else ""
        row.reasons.append(f"export: withheld by the workbench: {withheld or shown.notice}")
        return False
    stage = _settled_stage(shown)
    if stage == PASSED and shown.export is None:
        stage = ERROR
        row.reasons.append("export: the result screen showed no result")
    row.export = stage
    _note_export(shown, row, stage)
    return stage == PASSED


def _note_export(shown: ShownOutcome, row: PilotRow, stage: str) -> None:
    """Record what the settled export stage showed: the written file, or why it did not pass."""
    result = shown.export
    if stage == PASSED and result is not None:
        row.reasons.append(f"export: {result.export_format}, {result.byte_size} B, {result.completeness}")
    elif stage != PASSED:
        row.refusal_code = row.refusal_code or shown.code
        row.reasons.append(f"export: {shown.code} {shown.refusal or shown.notice}")


def _recorded(shown: ShownOutcome, row: PilotRow) -> bool:
    if shown.submitted and _settled_stage(shown) == PASSED:
        row.filed = True
        row.reasons.append("filed locally")
        return True
    row.reasons.append(f"file: {shown.code} {shown.refusal or shown.notice}")
    return False


def _stop(driver: WorkbenchDriver, row: PilotRow, action: ModeloFormNextAction | None) -> None:
    """Note the served step the pilot cannot take, and what the form asks to fill in."""
    if action is None or action is ModeloFormNextAction.RECORDED:
        return
    row.stopped_at = action.value
    missing = ", ".join(driver.shown_missing()) if action is ModeloFormNextAction.FILL else ""
    row.reasons.append(
        f"stopped: the served next action is {action.value}"
        + (f" (missing: {missing})" if missing else "")
        + f": {driver.notice()}"
    )


def stop_when_not_owed(row: PilotRow, *, owed: bool, calculated: bool, served: ModeloFormNextAction | None) -> bool:
    """Stop a return the table holds not owed once it calculated: it is neither checked, exported nor recorded.

    The table checks that the overview calendar suppresses such a return as not applicable and goes no further, so
    the pilot leaves it unfiled and its successors read the table's world. The row says what the form served next
    and was not taken. Returns whether the return stops here.
    """
    if owed or not calculated:
        return False
    row.verify = NOT_OWED
    row.export = NOT_REACHED
    next_step = "no next step" if served is None else f"the next step {served.value}"
    row.reasons.append(
        f"not owed: the table holds the return not owed, so the pilot stops after calculate; "
        f"the form serves {next_step}"
    )
    return True


def first_action(served: ModeloFormNextAction | None, *, calculated: bool) -> ModeloFormNextAction | None:
    """The step the drive starts with: the calculation, when the return holds one and the form does not offer it.

    The table calculates every return it created, and states what its calculation offers only after that
    calculation. A return whose carries were stated first holds a calculation already, since the guarded edit that
    states them calculates, so the form then serves the step after it (the check, or the finding to resolve) and
    nothing would make the statements. The workbench binds its calculate key whatever step it serves; the
    pilot presses it, as the table calculates.
    """
    if calculated and served not in _CALCULATE:
        return ModeloFormNextAction.RECALCULATE
    return served


async def _drive(driver: WorkbenchDriver, statements: _Statements, row: PilotRow, *, owed: bool = True) -> None:
    """Take each operation step the form serves, once per stage, until it serves none, or one does not pass.

    The first step is the calculation (:func:`first_action`). A return the table holds not owed (``owed`` false)
    is taken through calculate only.
    """
    taken: set[str] = set()
    action = first_action(driver.served_next_action(), calculated=driver.calculated())
    while True:
        stage = None if action is None else _STAGE_OF_ACTION.get(action)
        if action is None or stage is None or stage in taken:
            _stop(driver, row, action)
            return
        taken.add(stage)
        if not await _take_step(driver, statements, row, action, owed=owed):
            return
        action = driver.served_next_action()


async def _take_step(
    driver: WorkbenchDriver, statements: _Statements, row: PilotRow, action: ModeloFormNextAction, *, owed: bool
) -> bool:
    """Take one served step; whether the drive goes on to the next one."""
    if action in _CALCULATE:
        passed = await _calculate(driver, statements, action, row)
        if driver.calculated():
            row.figures = driver.shown_figures()
        if stop_when_not_owed(row, owed=owed, calculated=passed, served=driver.served_next_action()):
            return False
        return passed
    if action is ModeloFormNextAction.VERIFY:
        return _verified(await driver.press_for(action), row)
    if action in _EXPORT:
        return _exported(await driver.press_for(action), row)
    return _recorded(await driver.press_for(action), row)


def _refused_before_workbench(row: PilotRow, error: PersonaMaterialisationError, where: str) -> PilotRow:
    match = _SETTLED.match(str(error))
    row.calculate = REFUSED if match is not None else ERROR
    row.refusal_code = None if match is None else match["code"] or None
    row.reasons.append(f"{where}: {' '.join(str(error).split())[:_REASON_LIMIT]}")
    return row


def _create(world: PersonaWorld, plan: PlannedRow) -> str:
    created = settle_operation(
        world,
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        ModeloWorkCreateRequest(
            profile_id=world.profile_id,
            modelo=plan.modelo,
            period=PublicPeriod(filing_year=plan.year, code=plan.period),
            actor=PERSONA_ACTOR,
        ),
    )
    if not isinstance(created, ModeloWorkCreateProjection) or not isinstance(created.outcome, ModeloWorkCreateSuccess):
        outcome = getattr(created, "outcome", None)
        raise PersonaMaterialisationError(f"create refused: {getattr(outcome, 'reason', type(created).__name__)}")
    return created.outcome.unit.work_unit_id


def _answers(plan: PlannedRow, exports: Path) -> DialogAnswers:
    """What the persona answers in the workbench's dialogs, as the persona table states it.

    No joint return, the Modelo 390 exemption observed at the year's end, and the file for the AEAT.
    """
    return DialogAnswers(
        m303_joint_return_elected=False,
        m303_observed_at=datetime(plan.year, 12, 31, 12, tzinfo=UTC),
        export_artefact=ModeloExportArtefact.FICHERO_BOE,
        export_path=exports / f"{plan.persona}-{plan.modelo}-{plan.year}-{plan.period}.txt",
    )


async def _open_and_drive(
    materialised: MaterialisedPersona, plan: PlannedRow, work_unit_id: str, exports: Path, row: PilotRow
) -> None:
    statements = _statements(materialised, plan, work_unit_id)
    async with open_workbench(materialised.world, work_unit_id, _answers(plan, exports)) as driver:
        await _drive(driver, statements, row, owed=plan.owed)


def _run_return(materialised: MaterialisedPersona, plan: PlannedRow, exports: Path) -> PilotRow:
    """Create the return, state what the persona states before calculating it, then drive it through the workbench."""
    world = materialised.world
    row = PilotRow(persona=plan.persona, modelo=plan.modelo, year=plan.year, period=plan.period)
    if filing_key(plan.modelo, plan.year, plan.period) in materialised.filings:
        row.reasons.append("filed by the persona's history replay; the pilot does not drive it")
        return row
    try:
        work_unit_id = _create(world, plan)
    except PersonaMaterialisationError as error:
        return _refused_before_workbench(row, error, "create")
    try:
        if plan.modelo == "100":
            attest_prior_carries(materialised.persona, world, work_unit_id, plan.year)
        attest_before_first_calculation(
            world, modelo=plan.modelo, year=plan.year, period=plan.period, work_unit_id=work_unit_id
        )
        if world.work_inputs:
            enter_return_work_inputs(world, work_unit_id)
    except PersonaMaterialisationError as error:
        return _refused_before_workbench(row, error, "statement before calculating")
    exports.mkdir(parents=True, exist_ok=True)
    try:
        with override_settings(cadrumo_output_language="en"):
            asyncio.run(_open_and_drive(materialised, plan, work_unit_id, exports, row))
    except PersonaMaterialisationError as error:
        row.calculate = row.calculate if row.calculate not in {None, PASSED} else ERROR
        row.reasons.append(f"statement after calculating: {' '.join(str(error).split())[:_REASON_LIMIT]}")
    return row


def run_return(materialised: MaterialisedPersona, plan: PlannedRow, exports: Path) -> PilotRow:
    """Drive one return; a crash inside it is the return's own row, every stage an error, not the persona's end."""
    started = time.monotonic()
    try:
        row = _run_return(materialised, plan, exports)
    except Exception as crash:
        get_logger(__name__).error("TUI pilot crashed on %s: %s", plan.key, type(crash).__qualname__, exc_info=True)
        lines = str(crash).splitlines()
        row = PilotRow(
            persona=plan.persona,
            modelo=plan.modelo,
            year=plan.year,
            period=plan.period,
            calculate=ERROR,
            verify=ERROR,
            export=ERROR,
            cause=f"{CRASH_CAUSE}{type(crash).__qualname__}",
            cause_words=lines[0][:300] if lines else "",
        )
    row.calculate = row.calculate or NOT_REACHED
    row.verify = row.verify or NOT_REACHED
    row.export = row.export or NOT_REACHED
    row.seconds = time.monotonic() - started
    return row


# -- one persona ------------------------------------------------------------------------------------------------------


def _failed(table: TableRow, reason: str, cause: str) -> PilotRow:
    return PilotRow(
        persona=table.persona,
        modelo=table.modelo,
        year=table.year,
        period=table.period,
        calculate=ERROR,
        verify=NOT_REACHED,
        export=NOT_REACHED,
        reasons=[reason],
        cause=cause,
    )


def _reported(table: TableRow, row: PilotRow) -> ReportedRow:
    write_rows([row])
    return ReportedRow(table=table, row=row, outcome=outcome(row, table))


def run_persona(persona_id: str, tmp_path: Path) -> PersonaRun:
    """Replay the persona at each horizon the table reports its returns at, and drive every return in the workbench.

    With the intake file named, the persona's line is appended first and each reported return's row as soon as it
    finishes, so nothing a crash comes after is lost; the persona's line is appended again when the replays changed
    it.
    """
    envelope = pilot_envelope()
    persona = read_persona(persona_id, envelope=envelope)
    plan = pilot_plan(persona_id, table_rows_path(), envelope)
    loaded = PilotRow(persona=persona_id)
    write_rows([replace(loaded, reasons=[])])
    announced = (loaded.loads, list(loaded.reasons))
    reported: list[ReportedRow] = [
        _reported(
            table,
            _failed(
                table,
                f"the table reports it at horizon {table.horizon}, which does not owe it",
                "other:not_planned_at_horizon",
            ),
        )
        for table in plan.unplanned
    ]
    for replay in plan.replays:
        root = tmp_path / f"horizon-{replay.horizon}"
        done: set[tuple[str, str, int, str]] = set()
        try:
            with materialised_persona(
                persona_id, root, replay_scope(persona), reuse=True, horizon=replay.horizon
            ) as materialised:
                for block in materialised.not_loaded:
                    loaded.reasons.append(f"horizon {replay.horizon}: not loaded {block.block}: {block.reason}")
                ran: list[PilotRow] = []
                for planned in replay.returns:
                    row = run_return(materialised, planned, root / "exports")
                    if planned.key in replay.reported:
                        table = plan.expected[planned.key]
                        row.cause, row.cause_words = row_cause(row, table, ran)
                        note = export_unavailable_note(row, table)
                        if note is not None:
                            row.reasons.append(note)
                        done.add(planned.key)
                        reported.append(_reported(table, row))
                    else:
                        row.cause, row.cause_words = unreported_cause(row, ran)
                    ran.append(row)
        except (PersonaMaterialisationError, PersonaCatalogueError) as error:
            loaded.loads = False
            loaded.reasons.append(f"horizon {replay.horizon}: {' '.join(str(error).split())[:_REASON_LIMIT]}")
            reported += [
                _reported(
                    plan.expected[key],
                    _failed(plan.expected[key], f"replay under horizon {replay.horizon} failed", "other:replay_failed"),
                )
                for key in sorted(replay.reported - done)
            ]
    if (loaded.loads, loaded.reasons) != announced:
        write_rows([loaded])
    return PersonaRun(loaded=loaded, reported=tuple(reported))


def run_failures(run: PersonaRun) -> list[str]:
    """Each reported row the table counts as differing from its own, naming the row, its cause and what it said."""
    return [
        f"{item.row.label}: {item.outcome}: {item.row.reason()}" for item in run.reported if item.outcome == DIFFERS
    ]
