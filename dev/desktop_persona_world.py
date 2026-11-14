"""Materialise one catalogue persona into a storage root, with every return its table row runs ready to calculate.

The persona table replays a persona and takes each return it owes through create, calculate, verify, export and
local filing. The desktop window does calculate, verify and export itself, so this tool stops each return before
the calculate operation: it replays the persona's world with ``reuse=False`` into a caller-given directory, then,
in the table's own chain order, runs the table's preparation of every planned row (create, the pending carries
and prior figures the table states first and a Modelo 303's evidence) and records the statements the table's
calculate makes (the persona's work inputs, prior values, work-income statements and the pending rental carries)
through the table's own functions. Planning, scope, stated values, preparation and statements are the table's own.

The window enters the statements it has a door for. A pending-carry statement of nothing pending, a prior figure
and the work-income statement each have one on the declaration's form (the statements offer and the prior-values
offer), so the world does not record them: the row's ``window_statements`` carries each, taken from the table's own
statement readers, for the window to enter and calculate with. A work input, a pending carry stated as an amount
and a let property's carry have no such door; the world records those and every statement the table states before
the last of them, keeps the calculation that stores, and the row's ``no_window_door`` names each kind with the
operation that records it.

    python -m dev.desktop_persona_world --persona <id> --horizon <year> --storage-root <absolute directory>

The directory must be absent or empty and lie outside every Git project. One JSON object goes to standard output:
the ``CADRUMO_STORAGE_ROOT`` the packaged desktop must be started with, the profile id, where the profile
passphrase is defined (never the passphrase), the scenario instant, and one entry per planned row.

Every operation here ran under the persona's frozen scenario clock, as the table's calculate does; a desktop on the
wall clock calculates at a later instant. Each statement is recorded through a calculating edit, which stores a
calculation. A return that holds none after its recorded statements is left uncalculated (``driver_calculate`` is
``not_run``), so the window's calculate reads what it enters. A return that holds one anyway, because a statement
the window cannot enter was recorded through a calculating edit, reports ``calculate_inherited_reason`` naming the
kinds. A row is prepared against a profile in which the rows before it are not verified and filed locally, whereas
the table files each verified row before it creates the next; the window drives those rows itself, so they stay
unfiled here.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.application.modelo.operation_shared import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tests.persona_materialisation import (
    PersonaMaterialisationError,
    materialised_persona,
    year_envelope,
)
from cadrumo.tests.env_scope import scoped_env_var
from cadrumo.tests.personas import PersonaCatalogueError, persona_ids, read_persona

from .acceptance.persona_table.cli_column.world_report import Phase, Statement, StatementKind, statement_record
from .desktop_agent_live.disposable_root import enclosing_git_project
from .exit_codes import FAILED, OK
from .paths import STORAGE_ROOT_ENV

if TYPE_CHECKING:
    from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona

    from .acceptance.persona_table.rows import PlannedRow
    from .acceptance.persona_table.sweep import PreparedReturn

CREDENTIAL_SOURCE: Final = "persona_materialisation.PERSONA_PROFILE_CREDENTIAL"
"""Where the profile passphrase is defined; the tool never prints the passphrase itself."""
NOT_RUN: Final = "not_run"
"""The calculate outcome of a return left for the window to calculate."""
CALCULATING_EDIT_STAGES: Final = frozenset(
    {"prior_carries", "attested_prior_values", "work_inputs", "work_income_none", "rental_carries"}
)
"""The stages that record a statement through a calculating edit, which stores a calculation."""
STAGE_OF_KIND: Final = {
    StatementKind.PRIOR_CARRIES: "prior_carries",
    StatementKind.PRIOR_VALUE: "attested_prior_values",
    StatementKind.WORK_INCOME_NONE: "work_income_none",
}
"""The stage name of each statement kind the window can enter, as ``stages`` names the recorded ones."""
NEEDS_CALCULATION: Final = frozenset({Phase.AFTER_CALCULATION, Phase.AFTER_RECALCULATION})
"""The phases whose statements the table makes on a calculated return."""
TABLE_PERSONAS_ENV: Final = "PERSONA_TABLE_PERSONAS"
"""The variable the table's collector reads, at import, to name the personas it collects."""


def refuse_storage_root(root: Path) -> str | None:
    """Why ``root`` cannot hold a world, or ``None`` when it is an absolute, absent or empty directory outside Git."""
    if not root.is_absolute():
        return f"the storage root must be an absolute path: {root}"
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        return f"the storage root must be absent or an empty directory: {root}"
    project = enclosing_git_project(root)
    if project is not None:
        return f"the storage root {root} lies inside the Git project {project}"
    return None


def _entry(
    plan: PlannedRow,
    *,
    work_unit_id: str | None = None,
    prepared: bool = False,
    outcome: str | None = None,
    reason: str | None = None,
    m303_evidence: dict[str, str] | None = None,
    stages: Sequence[str] = (),
    calculate_outcome: str | None = None,
    calculate_inherited_reason: str | None = None,
    window_statements: Sequence[dict[str, Any]] = (),
    no_window_door: Sequence[dict[str, str]] = (),
) -> dict[str, Any]:
    """The report entry of one planned row: its work unit when prepared, else the stage where the table stops."""
    return {
        "modelo": plan.modelo,
        "year": plan.year,
        "period": plan.period,
        "owed": plan.owed,
        "work_unit_id": work_unit_id,
        "prepared": prepared,
        "pre_calculate_outcome": outcome,
        "reason": reason,
        "m303_evidence": m303_evidence,
        "stages": list(stages),
        "driver_calculate": calculate_outcome,
        "calculate_inherited_reason": calculate_inherited_reason,
        "window_statements": list(window_statements),
        "no_window_door": list(no_window_door),
    }


def _m303_evidence(prepared: PreparedReturn) -> dict[str, str] | None:
    """The Modelo 390 attestation the calculate request carries, or none outside the year's last period."""
    evidence = prepared.request.ordinary_m303_filing_evidence
    if evidence is None or evidence.m303_exonerado_390_attachment_id is None:
        return None
    return {
        "attachment_id": evidence.m303_exonerado_390_attachment_id,
        "sha256": str(evidence.m303_exonerado_390_sha256),
    }


@dataclass(frozen=True, slots=True)
class WindowSplit:
    """Which statements of one return the window enters, and which the world records."""

    left: frozenset[StatementKind] = frozenset()
    """The kinds the world does not record because the window enters them."""
    entered: tuple[Statement, ...] = ()
    """The statements the window enters, in the table's order, one per carry statement, figure and statement."""
    without_door: tuple[Statement, ...] = ()
    """The statements no window door enters, which the world records."""


def _has_window_door(statement: Statement) -> bool:
    """Whether the declaration's form lets the filer enter ``statement``.

    The statements offer states that no amount from earlier ejercicios is pending and the prior-values offer states
    a figure for an earlier return; the work-income statement is one of the statements offer's families. A carry
    stated as an amount, a casilla value and a let property's carry (a family stated per row, which the offer does
    not serve) have no such door.
    """
    if statement.refusal is not None:
        return False
    if statement.kind is StatementKind.PRIOR_CARRIES:
        return not statement.amounts and statement.gap is None
    return statement.kind in {StatementKind.PRIOR_VALUE, StatementKind.WORK_INCOME_NONE}


def window_split(materialised: MaterialisedPersona, plan: PlannedRow) -> WindowSplit:
    """Split the statements the table makes about ``plan``'s return between the window and the world.

    The world records every statement up to the last one the window has no door for, in the table's order, because
    each is a calculating edit and a later one reads the calculation of the earlier. The window enters the statements
    after it. A return with no such statement has all of its statements entered in the window.
    """
    from .acceptance.persona_table.cli_column.statements import statements_for

    try:
        made = statements_for(materialised, plan)
    except PersonaMaterialisationError:
        return WindowSplit()
    last = max((at for at, statement in enumerate(made) if not _has_window_door(statement)), default=-1)
    recorded_kinds = {statement.kind for statement in made[: last + 1]}
    entered: list[Statement] = []
    for statement in made[last + 1 :]:
        if statement.kind in recorded_kinds or not _has_window_door(statement):
            continue
        if any(item.kind is statement.kind and item.target == statement.target for item in entered):
            continue
        entered.append(statement)
    return WindowSplit(
        left=frozenset(statement.kind for statement in entered),
        entered=tuple(entered),
        without_door=tuple(statement for statement in made if not _has_window_door(statement)),
    )


def _window_statement(statement: Statement) -> dict[str, Any]:
    """The report record of a statement the window enters: the table's own, and whether it follows a calculation."""
    record: dict[str, Any] = dict(statement_record(statement))
    record["after_calculation"] = statement.phase in NEEDS_CALCULATION
    if statement.kind is StatementKind.WORK_INCOME_NONE:
        record["families"] = [AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED.value]
    return record


def _kind_names(split: WindowSplit) -> list[str]:
    """The kinds of statement the world records because the window has no door, each once."""
    return list(dict.fromkeys(statement.kind.value for statement in split.without_door))


def _without_door(split: WindowSplit) -> list[dict[str, str]]:
    """Each kind of statement the world records because the window has no door, with the operation that records it."""
    return [{"kind": kind, "operation": MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID} for kind in _kind_names(split)]


def _stage_names(
    materialised: MaterialisedPersona, plan: PlannedRow, prepared: PreparedReturn, left: frozenset[StatementKind]
) -> list[str]:
    """The names of the table's stages this return passes before calculate, from what the persona's world holds.

    A stage whose statements the window enters is not passed here.
    """
    world = materialised.world
    left_stages = {STAGE_OF_KIND[kind] for kind in left}
    stages = ["create"]
    if plan.modelo == "100":
        stages.append("prior_carries")
    if world.attested_prior_values:
        stages.append("attested_prior_values")
    if _m303_evidence(prepared) is not None:
        stages.append("m303_attestation")
    if world.work_inputs:
        stages.append("work_inputs")
    if world.work_income_none_statements:
        stages.append("work_income_none")
    if plan.modelo == "100":
        stages.append("rental_carries")
    return [stage for stage in stages if stage not in left_stages]


def _inherited_reason(split: WindowSplit, stages: Sequence[str], held_by_preparation: bool) -> str:
    """Why the return holds a calculation the window did not make, naming the kinds that no window door enters."""
    edits = ", ".join(stage for stage in stages if stage in CALCULATING_EDIT_STAGES) or "none"
    by = "the table's preparation" if held_by_preparation else "recording the statements"
    if not split.without_door:
        return f"{by} stored it through a calculating edit; edit stages: {edits}"
    return (
        f"no window door enters {', '.join(_kind_names(split))}; {by} stored the calculation through a "
        f"calculating edit ({MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID}); edit stages: {edits}"
    )


def _recorded(
    materialised: MaterialisedPersona, plan: PlannedRow, prepared: PreparedReturn, split: WindowSplit
) -> tuple[list[str], str, str | None]:
    """Record the statements the window has no door for, and those before them, and stop before the calculation.

    Returns the stages passed, the calculate outcome and why a calculation is held, if one is. The statements
    travel as calculating edits, which store a calculation: a work unit that holds one after them, or whose
    statements the form offers only on a calculated work unit, keeps the table's own calculate, and the reason
    names why. Any other work unit stays uncalculated and the window calculates it with the statements it enters.
    """
    from .acceptance.persona_table import sweep

    stages = _stage_names(materialised, plan, prepared, split.left)
    world = materialised.world
    held_by_preparation = sweep.holds_calculation(world, prepared.work_unit_id)
    try:
        sweep.record_statements(materialised, plan, prepared, left=split.left)
    except PersonaMaterialisationError:
        return stages, "refused", None
    if not sweep.holds_calculation(world, prepared.work_unit_id):
        awaiting = sweep.statements_needing_calculation(materialised, plan, left=split.left)
        if not awaiting:
            return stages, NOT_RUN, None
        reason = f"{', '.join(awaiting)} can only be stated on a calculated work unit"
        try:
            sweep._calculate(materialised, plan, prepared)  # the table's own calculate, not a copy
        except PersonaMaterialisationError:
            return [*stages, "calculate"], "refused", reason
        return [*stages, "calculate"], "calculated", reason
    return stages, "calculated", _inherited_reason(split, stages, held_by_preparation)


def _prepared_rows(materialised: MaterialisedPersona, plans: Sequence[PlannedRow]) -> list[dict[str, Any]]:
    """Run the table's preparation of each planned row, in chain order, and report where each one stands."""
    from .acceptance.persona_table import sweep
    from .acceptance.persona_table.rows import TableRow

    world = materialised.world
    rows: list[dict[str, Any]] = []
    for plan in plans:
        values = sweep.stated_values(materialised.persona, world.envelope, plan)
        split = window_split(materialised, plan)
        prepared = sweep.prepare_return(materialised, plan, values, left=split.left)
        if isinstance(prepared, TableRow):
            rows.append(_entry(plan, outcome=str(prepared.calculate), reason=prepared.reason or None))
            continue
        stages, calculate_outcome, inherited_reason = _recorded(materialised, plan, prepared, split)
        rows.append(
            _entry(
                plan,
                work_unit_id=prepared.work_unit_id,
                prepared=True,
                m303_evidence=_m303_evidence(prepared),
                stages=stages,
                calculate_outcome=calculate_outcome,
                calculate_inherited_reason=inherited_reason,
                window_statements=[_window_statement(statement) for statement in split.entered],
                no_window_door=_without_door(split),
            )
        )
    return rows


def prepare_world(persona_id: str, horizon: int, root: Path) -> dict[str, Any]:
    """Materialise ``persona_id`` under ``horizon`` into ``root``, prepare its rows and return the report.

    ``root`` is a checked, absent or empty directory; the profile stays in it when this returns.
    """
    with ExitStack() as scope:
        # Settings are read outside the isolated storage root while the world is registered; point that
        # read at a directory of its own, not at the checkout's default storage root.
        scope.enter_context(profile_adapter_composition())
        # The table runs on recorded ECB rates, as the repository's test composition binds them.
        scope.enter_context(bind_exchange_rate_provider_factory(recorded_ecb_rate_provider))
        ambient = scope.enter_context(tempfile.TemporaryDirectory(prefix="persona-world-"))
        scope.enter_context(scoped_env_var(STORAGE_ROOT_ENV, str(Path(ambient) / "storage")))
        # The table's collector parametrizes every persona it is allowed to collect when it is imported.
        scope.enter_context(scoped_env_var(TABLE_PERSONAS_ENV, persona_id))
        from .acceptance.persona_table import sweep

        scope.enter_context(scoped_env_var(sweep.MODELOS_ENV, None))
        scope.enter_context(scoped_env_var(sweep.YEARS_ENV, None))
        if sweep.PERSONAS_ENV != TABLE_PERSONAS_ENV:
            raise PersonaMaterialisationError(f"the table now reads its personas from {sweep.PERSONAS_ENV}")
        plans, _emitted = sweep.plan_rows(persona_id, horizon)
        with bundled_indexed_authority().operation() as operation:
            persona = read_persona(persona_id, envelope=year_envelope(operation))
        with materialised_persona(
            persona_id, root, sweep.replay_scope(persona), reuse=False, horizon=horizon
        ) as materialised:
            world = materialised.world
            rows = _prepared_rows(materialised, plans)
            report: dict[str, Any] = {
                "persona": persona_id,
                "horizon": horizon,
                "storage_root": str(world.storage_root.resolve()),
                "profile_id": str(world.profile_id),
                "passphrase_source": CREDENTIAL_SOURCE,
                "as_of": world.as_of.isoformat(),
                "authority_generation": world.operation.generation.logical_generation,
                "scope": materialised.scope.value,
                "rows": rows,
            }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare the persona's world, print the report as one JSON object and return the exit code."""
    parser = argparse.ArgumentParser(prog="python -m dev.desktop_persona_world", description=__doc__)
    parser.add_argument("--persona", required=True, help="a catalogue persona id")
    parser.add_argument("--horizon", required=True, type=int, help="a supported filing year the replay is run under")
    parser.add_argument("--storage-root", required=True, type=Path, help="an absolute, absent or empty directory")
    args = parser.parse_args(argv)
    if args.persona not in persona_ids():
        parser.error(f"unknown persona {args.persona!r}")
    refusal = refuse_storage_root(args.storage_root)
    if refusal is not None:
        parser.error(refusal)
    try:
        # Operations may print; standard output carries the report alone.
        with contextlib.redirect_stdout(sys.stderr):
            report = prepare_world(args.persona, args.horizon, args.storage_root.resolve())
    except (PersonaMaterialisationError, PersonaCatalogueError) as error:
        sys.stderr.write(f"persona world not prepared: {error}\n")
        return FAILED
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return OK


if __name__ == "__main__":
    sys.exit(main())
