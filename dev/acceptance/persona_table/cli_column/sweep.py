"""Sweep personas and horizons through the installed CLI of one snapshot, on one build, and resume where it stopped.

    python -m dev.acceptance.persona_table.cli_column.sweep --persona autonomo-alta-reciente \
        --tree <sha> --snapshot <dir>/snap-<sha> --authority <dir>/authority-<sha> \
        --client-root <checkout> --out <frontend dir>/cli-<sha>.jsonl

The horizons and the returns to drive come from the table's planner: every horizon of the registry envelope at which
the persona has a row the table writes, and those rows. The tree venv is built once and every case reuses it. Cases
run one after another, each on a fresh disposable root that is removed when its horizon is done. A horizon is skipped
when every one of its rows already has a line for the tree, or is named as not driven by the persona line of an
earlier run. The sweep stops at the first case that leaves an effect unsettled and keeps that root for inspection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.tests.personas import persona_ids
from dev.acceptance.installed_cli import InstalledCliError
from dev.exit_codes import FAILED, OK
from dev.packaging.acquire_common import venv_executable

from ..planner import registry_envelope
from ..rows import replay_horizons
from .case import (
    NOT_DRIVEN,
    CasePlace,
    CaseSpec,
    add_shared_arguments,
    drive_case,
    finish_case,
    log_dir_for,
    release_snapshot,
    run_redactor,
    unfiltered_plan,
)
from .driver import CaseSummary
from .hygiene import Redactor, SecretLeakError
from .intake import SURFACE, LineWriter
from .runtime import RuntimeSetupError, build_tree_venv, create_e2e_root, e2e_parent
from .world_report import ReturnKey

_HORIZON = re.compile(r"^horizon (?P<year>\d+): ")
_NOT_DRIVEN = re.compile(re.escape(NOT_DRIVEN) + r": (?P<keys>[^;]*)")
_KEY = re.compile(r"^(?P<modelo>\w+)/(?P<year>\d{4})/(?P<period>\w+)$")


@dataclass(frozen=True, slots=True)
class HorizonPlan:
    """One persona at one horizon: the returns the table writes a row for there."""

    persona: str
    horizon: int
    keys: frozenset[ReturnKey]


@dataclass(frozen=True, slots=True)
class Progress:
    """What the lines file already holds for a tree: the returns written and the ones a persona line named undriven."""

    written: frozenset[tuple[str, ReturnKey]] = frozenset()
    not_driven: frozenset[tuple[str, int, ReturnKey]] = frozenset()


@dataclass(frozen=True, slots=True)
class SweepSettings:
    """What a sweep runs and where its lines, build and snapshot are."""

    tree: str
    snapshot: Path
    authority: Path
    out: Path
    client_root: Path | None
    keep_snapshot: bool
    personas: tuple[str, ...]
    horizons: tuple[int, ...] = ()
    modelos: tuple[str, ...] = ()
    periods: tuple[str, ...] = ()
    root_parent: Path | None = None
    """The folder the disposable roots are made in; the account's temporary folder when unset."""


type Driver = Callable[[CaseSpec, Path, LineWriter, Redactor, CasePlace, frozenset[ReturnKey]], CaseSummary]
"""Run one case on a tree venv; :func:`drive_case` in a sweep, a stand-in in a test of the sweep's own logic."""


@dataclass(slots=True)
class SweepResult:
    """How a sweep ended: the horizons it drove, the ones already complete and where an unsettled effect stopped it."""

    driven: list[str] = field(default_factory=list)
    complete: list[str] = field(default_factory=list)
    stopped_at: str | None = None
    notes: list[str] = field(default_factory=list)


def label(plan: HorizonPlan) -> str:
    """``persona@horizon``, the name of a case."""
    return f"{plan.persona}@{plan.horizon}"


def _chosen_horizons(horizons: Sequence[int]) -> list[int]:
    """The registry envelope's replay horizons, newest first, narrowed to ``horizons`` when any are named."""
    available = replay_horizons(registry_envelope())
    unknown = sorted(set(horizons) - set(available))
    if unknown:
        raise ValueError(f"horizons {unknown} are outside the registry envelope {list(available)}")
    return [horizon for horizon in available if not horizons or horizon in horizons]


def _wanted(
    emitted: Iterable[tuple[str, str, int, str]], modelos: Sequence[str], periods: Sequence[str]
) -> frozenset[ReturnKey]:
    """The returns among the planner's emitted rows that pass the ``modelos`` and ``periods`` filters."""
    return frozenset(
        (modelo, year, period)
        for _persona, modelo, year, period in emitted
        if (not modelos or modelo in modelos) and (not periods or period in periods)
    )


def horizon_plans(
    personas: Sequence[str],
    *,
    horizons: Sequence[int] = (),
    modelos: Sequence[str] = (),
    periods: Sequence[str] = (),
) -> list[HorizonPlan]:
    """The cases to run: per persona, each replay horizon, newest first, at which the planner emits a wanted row.

    ``horizons`` narrows the registry envelope's horizons and is refused when it names one outside it; ``modelos``
    and ``periods`` narrow the rows. A persona and horizon without a wanted row is not a case.
    """
    chosen = _chosen_horizons(horizons)
    candidates = (
        HorizonPlan(persona, horizon, _wanted(unfiltered_plan(persona, horizon)[1], modelos, periods))
        for persona in personas
        for horizon in chosen
    )
    return [plan for plan in candidates if plan.keys]


def _named_keys(reason: str) -> frozenset[ReturnKey]:
    """The returns a persona line's reason names as not driven."""
    keys: set[ReturnKey] = set()
    found = _NOT_DRIVEN.search(reason)
    for item in () if found is None else found["keys"].split(","):
        match = _KEY.match(item.strip())
        if match is not None:
            keys.add((str(match["modelo"]), int(match["year"]), str(match["period"])))
    return frozenset(keys)


def _record(text: str) -> dict[str, object] | None:
    """The JSON object a line holds, or ``None`` for a blank or damaged line."""
    try:
        data: object = json.loads(text)
    except ValueError:
        return None
    return {str(name): value for name, value in data.items()} if isinstance(data, dict) else None


def _return_key(data: Mapping[str, object]) -> ReturnKey | None:
    """The return a line reports, or ``None`` for a persona line."""
    modelo, year, period = data.get("modelo"), data.get("year"), data.get("period")
    if isinstance(modelo, str) and isinstance(year, int) and isinstance(period, str):
        return (modelo, year, period)
    return None


def read_progress(path: Path, tree: str) -> Progress:
    """The returns of ``tree`` that ``path`` already holds a line for, and those its persona lines name undriven."""
    if not path.is_file():
        return Progress()
    written: set[tuple[str, ReturnKey]] = set()
    not_driven: set[tuple[str, int, ReturnKey]] = set()
    for text in path.read_text(encoding="utf-8").splitlines():
        data = _record(text)
        if data is None or data.get("surface") != SURFACE or data.get("tree") != tree:
            continue
        persona, key = str(data.get("persona")), _return_key(data)
        if key is not None:
            written.add((persona, key))
        elif (horizon := _HORIZON.match(str(data.get("reason", "")))) is not None:
            not_driven.update((persona, int(horizon["year"]), named) for named in _named_keys(str(data["reason"])))
    return Progress(frozenset(written), frozenset(not_driven))


def written_keys(plan: HorizonPlan, progress: Progress) -> frozenset[ReturnKey]:
    """The returns of ``plan`` that already have a line."""
    return frozenset(key for key in plan.keys if (plan.persona, key) in progress.written)


def is_complete(plan: HorizonPlan, progress: Progress) -> bool:
    """Whether every row of ``plan`` has a line or is named as not driven by an earlier persona line."""
    return all(
        (plan.persona, key) in progress.written or (plan.persona, plan.horizon, key) in progress.not_driven
        for key in plan.keys
    )


def venv_inside(snapshot: Path, venv: Path) -> Path:
    """``venv`` when it lies in the snapshot's build tree, so removing the snapshot removes it; else a refusal."""
    resolved = venv.resolve()
    if not resolved.is_relative_to(snapshot.resolve()):
        raise RuntimeSetupError(f"the tree venv {resolved} lies outside the snapshot {snapshot}")
    return resolved


class TreeVenv:
    """The tree venv of a sweep: built on first use, then reused by every case while its ``aeat`` launcher stands."""

    def __init__(self, snapshot: Path, build: Callable[[], Path]) -> None:
        """Remember ``snapshot`` and the ``build`` that makes the venv; nothing is built yet."""
        self._snapshot = snapshot
        self._build = build
        self._venv: Path | None = None
        self.builds = 0

    def path(self) -> Path:
        """The venv, built now when it was never built or its launcher is gone."""
        if self._venv is None or not venv_executable(self._venv, "aeat").is_file():
            self._venv = venv_inside(self._snapshot, self._build())
            self.builds += 1
        return self._venv


def _drive_horizon(
    settings: SweepSettings,
    plan: HorizonPlan,
    venv: TreeVenv,
    sinks: tuple[LineWriter, Redactor],
    drive: tuple[Driver, Progress],
) -> tuple[CaseSummary, list[str]]:
    """Run one case on a fresh root, remove the root unless the case stopped, and return what ended it."""
    writer, redactor = sinks
    driver, done = drive
    parent = e2e_parent() if settings.root_parent is None else settings.root_parent
    place = CasePlace(create_e2e_root(parent), log_dir_for(settings.out, settings.tree, plan.persona, plan.horizon))
    spec = CaseSpec(
        settings.tree,
        plan.persona,
        plan.horizon,
        settings.snapshot,
        settings.authority,
        modelos=settings.modelos,
        periods=settings.periods,
    )
    summary = CaseSummary()
    try:
        summary = driver(spec, venv.path(), writer, redactor, place, written_keys(plan, done))
    finally:
        notes = finish_case(place, redactor, keep_root=summary.stopped_at is not None, parent=parent)
    return summary, [*summary.notes, *notes]


def run_sweep(
    settings: SweepSettings,
    plans: Sequence[HorizonPlan],
    venv: TreeVenv,
    sinks: tuple[LineWriter, Redactor],
    driver: Driver = drive_case,
) -> SweepResult:
    """Drive the horizons that are not complete, in order; stop after the first case that left an effect unsettled."""
    result = SweepResult()
    progress = read_progress(settings.out, settings.tree)
    for plan in plans:
        if is_complete(plan, progress):
            result.complete.append(label(plan))
            continue
        summary, notes = _drive_horizon(settings, plan, venv, sinks, (driver, progress))
        result.driven.append(label(plan))
        result.notes.extend(f"{label(plan)}: {note}" for note in notes)
        if summary.stopped_at is not None:
            result.stopped_at = f"{label(plan)} at {'/'.join(map(str, summary.stopped_at))}"
            break
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dev.acceptance.persona_table.cli_column.sweep", description=__doc__
    )
    parser.add_argument(
        "--persona", action="append", default=[], help="a catalogue persona id (repeatable; default all)"
    )
    parser.add_argument("--horizon", action="append", default=[], type=int, help="a horizon (repeatable; default all)")
    add_shared_arguments(parser)
    return parser


def _settings(args: argparse.Namespace, parser: argparse.ArgumentParser) -> SweepSettings:
    known = persona_ids()
    unknown = [persona for persona in args.persona if persona not in known]
    if unknown:
        parser.error(f"unknown persona {unknown[0]!r}")
    return SweepSettings(
        args.tree,
        args.snapshot.resolve(),
        args.authority.resolve(),
        args.out.resolve(),
        args.client_root,
        args.keep_snapshot,
        tuple(args.persona) or tuple(known),
        horizons=tuple(args.horizon),
        modelos=tuple(args.modelo),
        periods=tuple(args.period),
    )


def _announce(result: SweepResult, redactor: Redactor) -> None:
    lines = [
        f"driven: {', '.join(result.driven) or 'none'}",
        f"already complete: {', '.join(result.complete) or 'none'}",
    ]
    if result.stopped_at is not None:
        lines.append(f"STOPPED, effect unsettled: {result.stopped_at}")
    for line in [*lines, *result.notes]:
        sys.stderr.write(redactor.text(line) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and sweep; the exit code is :data:`OK` when every driven case ran to its end."""
    parser = _parser()
    settings = _settings(parser.parse_args(argv), parser)
    redactor = run_redactor()
    build_log = settings.out.parent / "logs" / f"cli-{settings.tree}" / "build.log"

    def build() -> Path:
        return build_tree_venv(settings.snapshot, settings.authority, settings.client_root, redactor, build_log)

    result = SweepResult()
    status = FAILED
    try:
        plans = horizon_plans(
            settings.personas, horizons=settings.horizons, modelos=settings.modelos, periods=settings.periods
        )
        venv = TreeVenv(settings.snapshot, build)
        result = run_sweep(settings, plans, venv, (LineWriter(settings.out, redactor), redactor))
        status = OK if result.stopped_at is None else FAILED
    except (RuntimeSetupError, InstalledCliError, SecretLeakError, OSError, ValueError) as error:
        sys.stderr.write(f"CLI column sweep not finished: {redactor.error_text(error)}\n")
    finally:
        result.notes.extend(release_snapshot(settings.snapshot, keep=settings.keep_snapshot))
        _announce(result, redactor)
    return status


if __name__ == "__main__":
    sys.exit(main())
