"""One persona at one horizon on a disposable root: its world, the runtime that serves it, the driver and the lines.

``drive_case`` is the unit both the single-case entry point and the sweep run. It builds nothing: the tree venv is
made by the caller, once, and handed in. The root, the logs and the snapshot are released by the caller too, with
:func:`finish_case` and :func:`release_snapshot`, so the root of a case that left an effect unsettled can stay.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from cadrumo.entrypoints.cli.tests.cli_runner import cadrumo_click_command
from cadrumo.entrypoints.tests.persona_materialisation import PERSONA_PROFILE_CREDENTIAL
from cadrumo.tests.env_scope import scoped_env_var
from dev.acceptance.installed_cli import authority_generation

from ..export_check import export_reason
from ..planner import MODELOS_ENV, YEARS_ENV, persona_under_horizon, plan_rows, registry_envelope, stated_values
from ..rows import PlannedRow
from .driver import (
    CalculateMode,
    Case,
    CaseSummary,
    ExportCheck,
    Runner,
    Selection,
    Trace,
    bind_profile,
    profile_check,
    run_case,
    select_rows,
)
from .hygiene import Redactor, remove_secret_bearing
from .intake import LineWriter, Outcome, persona_line
from .row_form import form_leaf_present
from .runtime import RuntimeSetupError, e2e_parent, remove_snapshot, run_world, served_root, teardown_root
from .world_report import ReturnKey, RowPlan, WorldReport

NOT_DRIVEN = "not driven"
"""The words that name the returns the driver cannot run yet; the sweep reads the keys that follow them back."""
_STORAGE = "runtime"
_EXPORTS = "exports"


@dataclass(frozen=True, slots=True)
class CaseSpec:
    """Which persona is driven at which horizon, on which tree, and which of its returns are wanted."""

    tree: str
    persona: str
    horizon: int
    snapshot: Path
    authority: Path
    modelos: tuple[str, ...] = ()
    periods: tuple[str, ...] = ()
    keys: frozenset[ReturnKey] | None = None
    """The exact returns wanted, when a keys file names them; ``None`` wants every return the other filters pass."""
    calculate: CalculateMode = CalculateMode.AS_RUN


@dataclass(frozen=True, slots=True)
class CasePlace:
    """Where a case lives: its disposable root and the directory its logs go to."""

    root: Path
    log_dir: Path


def add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments the single-case entry point and the sweep share."""
    parser.add_argument("--tree", required=True, help="the commit the snapshot was taken from")
    parser.add_argument("--snapshot", required=True, type=Path, help="the snapshot directory, named snap-*")
    parser.add_argument("--authority", required=True, type=Path, help="the directory holding the published authority")
    parser.add_argument("--out", required=True, type=Path, help="the cli-<tree>.jsonl file the lines are appended to")
    parser.add_argument("--modelo", action="append", default=[], help="a modelo to drive (repeatable)")
    parser.add_argument("--period", action="append", default=[], help="a period to report (repeatable)")
    parser.add_argument("--client-root", type=Path, default=None, help="the checkout whose env/.env holds the client")
    parser.add_argument("--keep-snapshot", action="store_true", help="do not remove the snapshot at the end")
    parser.add_argument(
        "--calculate",
        type=CalculateMode,
        choices=list(CalculateMode),
        default=CalculateMode.AS_RUN,
        help="as-run sends calculate after the statements (default); read-back reads the statement's own"
        " calculation instead, as a diagnosis, and marks the row with a workaround",
    )


class _Trace:
    """The case log: one line per command, holding its label, how it ended and its served code; no result values."""

    def __init__(self, path: Path, redactor: Redactor) -> None:
        self._path = path
        self._redactor = redactor
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, label: str, outcome: Outcome) -> None:
        record = {"step": label, "kind": outcome.kind.value, "code": outcome.code, "operation_id": outcome.operation_id}
        text = self._redactor.text(json.dumps(record, ensure_ascii=False))
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text + "\n")


def unfiltered_plan(persona_id: str, horizon: int) -> tuple[list[PlannedRow], frozenset[tuple[str, str, int, str]]]:
    """The table's plan of ``persona_id`` under ``horizon`` with the environment's table filters lifted.

    The filters narrow the rows a table run writes; the CLI column's own filters are applied by its caller.
    """
    with ExitStack() as scope:
        scope.enter_context(scoped_env_var(MODELOS_ENV, None))
        scope.enter_context(scoped_env_var(YEARS_ENV, None))
        return plan_rows(persona_id, horizon)


def export_check_for(persona_id: str, horizon: int) -> ExportCheck:
    """The table's own checks of a written fichero for ``persona_id`` under ``horizon``: text rules, then readback.

    The check finds the planned return the driver named, takes the persona's stated values in force for it under the
    registry envelope and returns the first defect of the file, or an empty string when it is clean. It returns
    ``None`` when the replay plans no such return, which leaves the export stage an ``error`` rather than a ``pass``.
    Nothing is planned until the first file is checked.
    """

    @cache
    def planned() -> dict[tuple[str, int, str], PlannedRow]:
        rows, _emitted = unfiltered_plan(persona_id, horizon)
        return {(row.modelo, row.year, row.period): row for row in rows}

    def check(plan: RowPlan, output: Path) -> str | None:
        row = planned().get(plan.key)
        if row is None:
            return None
        values = stated_values(persona_under_horizon(persona_id, horizon), registry_envelope(), row)
        return export_reason(row, values, output)

    return check


def build_case(
    spec: CaseSpec,
    *,
    report: WorldReport,
    runner: Runner,
    exports: Path,
    writer: LineWriter,
    log: str,
    trace: Trace,
    done: frozenset[ReturnKey] = frozenset(),
) -> Case:
    """The case to run: the world, the runner, where files and lines go, and the table's export checks."""
    return Case(
        spec.tree,
        report,
        runner,
        exports,
        writer,
        log,
        export_check=export_check_for(spec.persona, spec.horizon),
        trace=trace,
        done=done,
        calculate=spec.calculate,
        form_door=form_leaf_present(cadrumo_click_command()),
    )


def not_driven_clause(selection: Selection) -> str:
    """The sentence that names every return left out, then the first reasons; empty when none is left out."""
    if not selection.skipped:
        return ""
    keys = ", ".join("/".join(map(str, key)) for key, _ in selection.skipped)
    reasons = "; ".join(f"{'/'.join(map(str, key))} ({why})" for key, why in selection.skipped[:3])
    return f"{NOT_DRIVEN}: {keys}; first reasons: {reasons}"


def seeding_reason(report: WorldReport, profile: str | None, generation: str, selection: Selection) -> str:
    """The persona line's reason: how the world was seeded, on which authority generation, what is not driven."""
    parts = [
        f"horizon {report.horizon}: world seeded in process through registered operations for the exact profile the"
        f" runtime serves ({profile or 'unknown'}); authority generation {generation}; passphrase per command on stdin"
    ]
    if report.aeat_filings_in_process:
        parts.append("live.filed-capture.single has no CLI door: the recorded AEAT filings were seeded in process")
    if clause := not_driven_clause(selection):
        parts.append(clause)
    return "; ".join(parts)


def _storage_of(report: WorldReport, root: Path) -> Path:
    """The storage root the world reports, which must lie below the disposable ``root`` the runtime may serve."""
    storage = Path(report.storage_root)
    if not storage.is_relative_to(root.resolve()):
        raise RuntimeSetupError("the world reported a storage root outside the disposable root")
    return storage


def _not_loaded(spec: CaseSpec, writer: LineWriter, reason: str, log: str) -> CaseSummary:
    """Write the persona line of a case that did not load, and report the case as ended without returns."""
    text = f"horizon {spec.horizon}: {reason}"
    writer.write(persona_line(tree=spec.tree, persona=spec.persona, loads=False, reason=text, log=log))
    return CaseSummary(notes=(text,))


def drive_case(
    spec: CaseSpec,
    template: Path,
    writer: LineWriter,
    redactor: Redactor,
    place: CasePlace,
    done: frozenset[ReturnKey] = frozenset(),
) -> CaseSummary:
    """Materialise, serve and drive one case on the tree venv ``template``; write its persona line and return lines.

    A world that cannot be materialised is a persona line that does not load, not an abort. ``done`` holds the
    returns whose lines already exist: they run, because the chain needs them, but are not written again.
    """
    log = str(place.log_dir / "case.log")
    filters = (spec.modelos, ())
    try:
        report = run_world(
            spec.snapshot, spec.authority, place.root / _STORAGE, spec.persona, spec.horizon, filters, redactor
        )
    except RuntimeSetupError as error:
        return _not_loaded(spec, writer, redactor.text(str(error)), log)
    storage = _storage_of(report, place.root)
    published = authority_generation(spec.authority)
    if published != report.authority_generation:
        reason = f"authority generation mismatch: world {report.authority_generation}, runtime {published}"
        return _not_loaded(spec, writer, reason, log)
    selection = select_rows(report, modelos=spec.modelos, periods=spec.periods, keys=spec.keys)
    served_log = place.log_dir / "runtime.stderr.log"
    with served_root(template, storage, spec.authority, PERSONA_PROFILE_CREDENTIAL, served_log) as runner:
        loads, why, profile = profile_check(runner)
        if not loads or profile is None:
            return _not_loaded(spec, writer, why, log)
        reason = seeding_reason(report, profile, published, selection)
        writer.write(persona_line(tree=spec.tree, persona=spec.persona, loads=True, reason=reason, log=log))
        exports = place.root / _EXPORTS
        exports.mkdir()
        case = build_case(
            spec,
            report=report,
            runner=bind_profile(runner, profile),
            exports=exports,
            writer=writer,
            log=log,
            trace=_Trace(place.log_dir / "case.log", redactor),
            done=done,
        )
        return run_case(case, selection)


def finish_case(place: CasePlace, redactor: Redactor, *, keep_root: bool, parent: Path | None = None) -> list[str]:
    """Remove the case's root unless it is kept as evidence, then sweep its logs for a secret; name what stayed.

    The root goes through :func:`teardown_root`, which refuses anything not named like a disposable root, not
    directly below ``parent`` (the account's temporary folder by default) or linked.
    """
    notes: list[str] = []
    if keep_root:
        notes.append(f"root kept for evidence: {place.root}")
    else:
        notes.extend(teardown_root(place.root, e2e_parent() if parent is None else parent))
    notes.extend(remove_secret_bearing(place.log_dir, redactor))
    return notes


def release_snapshot(snapshot: Path, *, keep: bool) -> list[str]:
    """Remove the snapshot, which holds the build's OAuth client, unless ``keep``; name everything that stayed."""
    if keep:
        return [f"snapshot kept: {snapshot}"]
    os.chdir(snapshot.parent)
    return remove_snapshot(snapshot)


def log_dir_for(out: Path, tree: str, persona: str, horizon: int) -> Path:
    """The directory a case's logs go to, beside the lines file."""
    return out.resolve().parent / "logs" / f"cli-{tree}" / f"{persona}@{horizon}"


def run_redactor(environment: Mapping[str, str] | None = None) -> Redactor:
    """The redactor of a run: the persona passphrase and the OAuth client ``environment`` holds, if any."""
    return Redactor.for_run(PERSONA_PROFILE_CREDENTIAL, os.environ if environment is None else environment)
