"""Run one persona at one horizon through the installed CLI of a snapshot of the tree, and write the CLI column's lines.

    python -m dev.acceptance.persona_table.cli_column --persona autonomo-alta-reciente --horizon <year> \
        --tree <sha> --snapshot <dir>/snap-<sha> --authority <dir>/authority-<sha> \
        --modelo 130 --modelo 303 --period 1T --out <frontend dir>/cli-<sha>.jsonl

Run it from the snapshot (``PYTHONPATH`` the snapshot's ``src`` and root) with the interpreter that runs the table. It
materialises the persona's world in an interpreter of its own, builds the snapshot into an installed wheel, serves a
fresh ``cadrumo-e2e-*`` root with a caller-owned runtime, drives each return through ``aeat app modelo work ...`` and
appends the intake lines to ``--out``. The snapshot is removed at the end, because the build leaves the publisher's
Google OAuth client in it; ``--keep-snapshot`` keeps it for a failed run. The root is kept, and named, only when a
command left its effect unsettled.

The OAuth client comes from ``CADRUMO_GOOGLE_OAUTH_CLIENT_JSON`` in the environment or from ``env/.env`` under
``--client-root``; it enters the wheel build's environment alone and is never written to a line, log or message.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from contextlib import ExitStack
from functools import cache
from pathlib import Path

from cadrumo.entrypoints.tests.persona_materialisation import PERSONA_PROFILE_CREDENTIAL
from cadrumo.tests.env_scope import scoped_env_var
from dev.acceptance.installed_cli import InstalledCliError, authority_generation
from dev.exit_codes import FAILED, OK

from ..export_check import export_reason
from ..planner import MODELOS_ENV, YEARS_ENV, persona_under_horizon, plan_rows, registry_envelope, stated_values
from ..rows import PlannedRow
from .driver import Case, CaseSummary, ExportCheck, Runner, Selection, Trace, profile_check, run_case, select_rows
from .hygiene import Redactor, SecretLeakError, remove_secret_bearing
from .intake import LineWriter, Outcome, persona_line
from .runtime import (
    RuntimeSetupError,
    build_tree_venv,
    create_e2e_root,
    e2e_parent,
    remove_snapshot,
    run_world,
    served_root,
    teardown_root,
)
from .world_report import RowPlan, WorldReport

_STORAGE = "runtime"
_EXPORTS = "exports"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dev.acceptance.persona_table.cli_column", description=__doc__)
    parser.add_argument("--persona", required=True, help="a catalogue persona id")
    parser.add_argument("--horizon", required=True, type=int, help="a supported filing year the replay is run under")
    parser.add_argument("--tree", required=True, help="the commit the snapshot was taken from")
    parser.add_argument("--snapshot", required=True, type=Path, help="the snapshot directory, named snap-*")
    parser.add_argument("--authority", required=True, type=Path, help="the directory holding the published authority")
    parser.add_argument("--out", required=True, type=Path, help="the cli-<tree>.jsonl file the lines are appended to")
    parser.add_argument("--modelo", action="append", default=[], help="a modelo to drive (repeatable)")
    parser.add_argument("--year", action="append", default=[], type=int, help="a filing year to drive (repeatable)")
    parser.add_argument("--period", action="append", default=[], help="a period to report (repeatable)")
    parser.add_argument("--client-root", type=Path, default=None, help="the checkout whose env/.env holds the client")
    parser.add_argument("--keep-snapshot", action="store_true", help="do not remove the snapshot at the end")
    return parser


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


def export_check_for(persona_id: str, horizon: int) -> ExportCheck:
    """The table's own checks of a written fichero for ``persona_id`` under ``horizon``: text rules, then readback.

    The check finds the planned return the driver named, takes the persona's stated values in force for it under the
    registry envelope and returns the first defect of the file, or an empty string when it is clean. It returns
    ``None`` when the replay plans no such return, which leaves the export stage an ``error`` rather than a ``pass``.
    Nothing is planned until the first file is checked.
    """

    @cache
    def planned() -> dict[tuple[str, int, str], PlannedRow]:
        # The environment's table filters narrow the replay's rows; the check needs the full plan of the persona.
        with ExitStack() as scope:
            scope.enter_context(scoped_env_var(MODELOS_ENV, None))
            scope.enter_context(scoped_env_var(YEARS_ENV, None))
            rows, _emitted = plan_rows(persona_id, horizon)
        return {(row.modelo, row.year, row.period): row for row in rows}

    def check(plan: RowPlan, output: Path) -> str | None:
        row = planned().get(plan.key)
        if row is None:
            return None
        values = stated_values(persona_under_horizon(persona_id, horizon), registry_envelope(), row)
        return export_reason(row, values, output)

    return check


def build_case(
    args: argparse.Namespace,
    *,
    report: WorldReport,
    runner: Runner,
    exports: Path,
    writer: LineWriter,
    log: str,
    trace: Trace,
) -> Case:
    """The case to run: the world, the runner, where files and lines go, and the table's export checks."""
    return Case(
        args.tree,
        report,
        runner,
        exports,
        writer,
        log,
        export_check=export_check_for(args.persona, args.horizon),
        trace=trace,
    )


def seeding_reason(report: WorldReport, profile: str | None, generation: str, selection: Selection) -> str:
    """The persona line's reason: how the world was seeded, on which authority generation, what is not driven."""
    parts = [
        "world seeded in process through registered operations for the exact profile the runtime serves"
        f" ({profile or 'unknown'}); authority generation {generation}; passphrase per command on stdin"
    ]
    if report.aeat_filings_in_process:
        parts.append("live.filed-capture.single has no CLI door: the recorded AEAT filings were seeded in process")
    if selection.skipped:
        named = ", ".join(f"{'/'.join(map(str, key))} ({why})" for key, why in selection.skipped[:4])
        parts.append(f"not driven: {len(selection.skipped)} returns: {named}")
    return "; ".join(parts)


def _drive(args: argparse.Namespace, redactor: Redactor, root: Path, log_dir: Path) -> CaseSummary:
    """Materialise, build, serve and drive one case; the persona line and a line per wanted return are written."""
    writer = LineWriter(args.out, redactor)
    log = str(log_dir / "case.log")
    storage = root / _STORAGE
    report = run_world(
        args.snapshot, args.authority, storage, args.persona, args.horizon, (args.modelo, args.year), redactor
    )
    published = authority_generation(args.authority)
    selection = select_rows(report, modelos=args.modelo, periods=args.period)
    if published != report.authority_generation:
        reason = f"authority generation mismatch: world {report.authority_generation}, runtime {published}"
        writer.write(persona_line(tree=args.tree, persona=args.persona, loads=False, reason=reason, log=log))
        return CaseSummary()
    template = build_tree_venv(args.snapshot, args.authority, args.client_root, redactor, log_dir / "build.log")
    with served_root(
        template, storage, args.authority, PERSONA_PROFILE_CREDENTIAL, log_dir / "runtime.stderr.log"
    ) as runner:
        loads, why, profile = profile_check(runner)
        reason = seeding_reason(report, profile, published, selection) if loads else why
        writer.write(persona_line(tree=args.tree, persona=args.persona, loads=loads, reason=reason, log=log))
        if not loads:
            return CaseSummary()
        exports = root / _EXPORTS
        exports.mkdir()
        trace = _Trace(log_dir / "case.log", redactor)
        case = build_case(args, report=report, runner=runner, exports=exports, writer=writer, log=log, trace=trace)
        return run_case(case, selection)


def _finish(args: argparse.Namespace, redactor: Redactor, root: Path, log_dir: Path, *, keep_root: bool) -> list[str]:
    """Tear down the root, sweep the logs for a secret and remove the snapshot; name everything that stayed."""
    notes: list[str] = []
    if keep_root:
        notes.append(f"root kept for evidence: {root}")
    else:
        notes.extend(teardown_root(root, e2e_parent()))
    notes.extend(remove_secret_bearing(log_dir, redactor))
    os.chdir(args.snapshot.parent)
    if args.keep_snapshot:
        notes.append(f"snapshot kept: {args.snapshot}")
    else:
        notes.extend(remove_snapshot(args.snapshot))
    return notes


def run(args: argparse.Namespace) -> int:
    """Run the case, always tearing down; the exit code is :data:`OK` when the case ran to its end."""
    redactor = Redactor.for_run(PERSONA_PROFILE_CREDENTIAL, os.environ)
    args.snapshot, args.authority = args.snapshot.resolve(), args.authority.resolve()
    log_dir = args.out.resolve().parent / "logs" / f"cli-{args.tree}" / f"{args.persona}@{args.horizon}"
    root = create_e2e_root(e2e_parent())
    summary = CaseSummary()
    status = FAILED
    try:
        summary = _drive(args, redactor, root, log_dir)
        status = OK
    except (RuntimeSetupError, InstalledCliError, SecretLeakError, OSError) as error:
        sys.stderr.write(f"CLI column not run: {redactor.error_text(error)}\n")
    finally:
        for note in _finish(args, redactor, root, log_dir, keep_root=summary.stopped_at is not None):
            sys.stderr.write(redactor.text(note) + "\n")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run one case."""
    return run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
