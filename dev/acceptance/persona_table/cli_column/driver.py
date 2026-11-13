"""Drive a persona's returns through the installed ``aeat`` command line: create, calculate, verify, export, file.

Every step is one fresh ``aeat`` process; the driver reads the envelope it printed, maps it to the intake vocabulary
(``intake``) and goes on. It states no tax fact: the arguments it sends are the report's coordinates and the ids the
previous command printed. A command whose effect is not settled stops the chain, because the filed state of the
persona is then not known, and a mutation is never sent twice.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .intake import (
    Kind,
    LineWriter,
    Outcome,
    ReturnScope,
    RowResult,
    StageResult,
    calculate_stage,
    classify,
    export_stage,
    failed,
    file_stage,
    return_line,
    verify_stage,
)
from .world_report import ReturnKey, RowPlan, WorldReport

SUPPORTED_MODELOS = frozenset({"130", "303"})
"""The returns this driver runs end to end; the others need the pre-calculation statements or the calendar read."""
FILING_NOTE = "Synthetic local pending filing only; not sent to AEAT"
_M303 = "303"
_WORK = ("app", "modelo", "work")


class Runner(Protocol):
    """Run one ``aeat`` command and return the JSON envelope it printed, or ``None`` when it printed none."""

    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object] | None:
        """Run ``args`` in a fresh process; the profile passphrase, when ``authenticated``, goes on its stdin only."""
        ...


type ExportCheck = Callable[[RowPlan, Path], str | None]
"""The table's own checks of a written fichero: empty when clean, the defect when not, ``None`` when unavailable."""
type Trace = Callable[[str, Outcome], None]


def _no_trace(_label: str, _outcome: Outcome) -> None:
    return None


@dataclass(frozen=True, slots=True)
class Case:
    """One persona on one world: what to run, how to run a command, and where the lines go."""

    tree: str
    report: WorldReport
    runner: Runner
    exports: Path
    writer: LineWriter
    log: str
    export_check: ExportCheck | None = None
    trace: Trace = _no_trace
    done: frozenset[ReturnKey] = frozenset()
    """The returns whose lines already exist: they still run, since the chain needs them, but are not written."""


@dataclass(frozen=True, slots=True)
class Selection:
    """The returns a run takes, in chain order, and those it leaves out with the reason."""

    run: tuple[RowPlan, ...]
    wanted: frozenset[ReturnKey]
    skipped: tuple[tuple[ReturnKey, str], ...]


@dataclass(frozen=True, slots=True)
class CaseSummary:
    """What a case wrote: the returns it reported, where an unsettled effect stopped it, what it left out."""

    written: tuple[ReturnKey, ...] = ()
    stopped_at: ReturnKey | None = None
    skipped: tuple[tuple[ReturnKey, str], ...] = ()
    notes: tuple[str, ...] = field(default=())


def unsupported_reason(plan: RowPlan, report: WorldReport) -> str | None:
    """Why the driver cannot run ``plan`` yet, or ``None`` when it can."""
    if not plan.owed:
        return "stated not owed: needs the overview calendar read"
    if report.needs_statements:
        return "the persona states values the table enters before it calculates"
    if plan.modelo not in SUPPORTED_MODELOS:
        return f"Modelo {plan.modelo} is not driven yet"
    return None


def _wanted(report: WorldReport, modelos: Sequence[str], periods: Sequence[str]) -> frozenset[ReturnKey]:
    return frozenset(
        plan.key
        for plan in report.rows
        if plan.emitted and (not modelos or plan.modelo in modelos) and (not periods or plan.period in periods)
    )


def select_rows(report: WorldReport, *, modelos: Sequence[str] = (), periods: Sequence[str] = ()) -> Selection:
    """The returns to run: every wanted return and the supported replayed ones before the last of them.

    A return is wanted when the table writes a row for it and it passes the ``modelos`` and ``periods`` filters. A
    history-filed return is neither run nor reported; a return the driver cannot run is left out with the reason.
    """
    wanted = _wanted(report, modelos, periods)
    last = max((index for index, plan in enumerate(report.rows) if plan.key in wanted), default=-1)
    candidates = [plan for plan in report.rows[: last + 1] if not plan.history_filed]
    reasons = [(plan, unsupported_reason(plan, report)) for plan in candidates]
    run = tuple(plan for plan, reason in reasons if reason is None)
    skipped = tuple((plan.key, reason) for plan, reason in reasons if reason is not None)
    return Selection(run, wanted, skipped)


def create_args(plan: RowPlan, actor: str) -> list[str]:
    """The arguments that create the work unit of ``plan``."""
    return [
        *_WORK,
        "create",
        "--modelo",
        plan.modelo,
        "--year",
        str(plan.year),
        "--period",
        plan.period,
        "--by",
        actor,
    ]


def export_path(exports: Path, persona: str, plan: RowPlan) -> Path:
    """Where the fichero of ``plan`` is written, named as the table names it."""
    return exports / f"{persona}-{plan.modelo}-{plan.year}-{plan.period}.txt"


def _step(case: Case, label: str, args: Sequence[str], *, authenticated: bool = True) -> Outcome:
    outcome = classify(case.runner(args, authenticated=authenticated))
    case.trace(label, outcome)
    return outcome


def _printed(outcome: Outcome, name: str) -> str | None:
    value = outcome.result.get(name)
    return value if isinstance(value, str) and value else None


def _evidence_args(case: Case, plan: RowPlan) -> list[str] | StageResult:
    """The Modelo 303 evidence arguments, or the calculate stage when the annual attestation was refused.

    No joint return is elected; in the year's last owed period the attestation the world records is made first and
    its printed attachment goes on the calculation.
    """
    if plan.modelo != _M303:
        return []
    if plan.period != plan.last_owed_period:
        return ["--no-joint-return-elected"]
    attestation = [*_WORK, "attest-m303-exonerado-390", "--year", str(plan.year), "--period", plan.period]
    observed = ["--observed-at", f"{plan.year}-12-31T12:00Z", "--by", case.report.actor]
    attested = _step(case, "attest-m303-exonerado-390", [*attestation, *observed])
    if attested.kind is not Kind.OK:
        return failed(attested, "attest-m303-exonerado-390")
    attachment, digest = _printed(attested, "attachment_id"), _printed(attested, "sha256")
    if attachment is None or digest is None:
        return StageResult("error", reason="attest-m303-exonerado-390 printed no attachment_id and sha256")
    evidence = ["--m303-exonerado-390-attachment-id", attachment, "--m303-exonerado-390-sha256", digest]
    return ["--no-joint-return-elected", *evidence]


def _created(case: Case, plan: RowPlan) -> str | StageResult:
    """The new work unit's id, or the calculate stage of a create that published none."""
    created = _step(case, "create", create_args(plan, case.report.actor))
    if created.kind is not Kind.OK:
        return failed(created, "create")
    work_unit_id = _printed(created, "work_unit_id")
    return work_unit_id or StageResult("error", reason="create printed no work_unit_id")


def run_return(case: Case, plan: RowPlan) -> RowResult:
    """Create, calculate, verify, export and file one return; the result records where it stopped and why."""
    work_unit_id = _created(case, plan)
    if isinstance(work_unit_id, StageResult):
        return RowResult(work_unit_id)
    evidence = _evidence_args(case, plan)
    if isinstance(evidence, StageResult):
        return RowResult(evidence)
    calculated = _step(case, "calculate", [*_WORK, "calculate", work_unit_id, *evidence, "--by", case.report.actor])
    calculate, figures = calculate_stage(calculated)
    revision_id = _printed(calculated, "calculation_revision_id")
    if calculated.kind is not Kind.OK:
        return RowResult(calculate, figures=figures)
    if revision_id is None:
        return RowResult(StageResult("error", reason="calculate printed no calculation_revision_id"), figures=figures)
    return _lifecycle(case, plan, work_unit_id, revision_id, RowResult(calculate, figures=figures))


def _lifecycle(case: Case, plan: RowPlan, work_unit_id: str, revision_id: str, calculated: RowResult) -> RowResult:
    """Verify, then export, then file a calculated return, in the table's lifecycle order.

    Export runs whatever verify settled; filing needs a granted verification, whatever export settled. Nothing
    runs after an unsettled effect.
    """
    actor = case.report.actor
    verified = _step(case, "verify", [*_WORK, "verify", revision_id, "--by", actor])
    result = RowResult(calculated.calculate, verify_stage(verified), figures=calculated.figures)
    if verified.kind is Kind.UNKNOWN:
        return result
    exported = _step(case, "export", _export_args(case, plan, work_unit_id))
    result = RowResult(result.calculate, result.verify, _export_stage(case, plan, exported), figures=result.figures)
    if exported.kind is Kind.UNKNOWN or verified.result.get("granted_verificado_completo") is not True:
        return result
    note = ["--notes", FILING_NOTE]
    filed = _step(case, "file", [*_WORK, "file", revision_id, "--by", actor, *note])
    return RowResult(result.calculate, result.verify, result.export, file_stage(filed), result.figures)


def _export_args(case: Case, plan: RowPlan, work_unit_id: str) -> list[str]:
    output = export_path(case.exports, case.report.persona, plan)
    return ["app", "modelo", "export", work_unit_id, "--output", str(output), "--by", case.report.actor]


def _export_stage(case: Case, plan: RowPlan, exported: Outcome) -> StageResult:
    """The export stage: the command's outcome and, for a written file, the table's checks of its bytes."""
    if exported.kind is not Kind.OK:
        return export_stage(exported, "")
    output = export_path(case.exports, case.report.persona, plan)
    if not output.is_file():
        return export_stage(exported, "export: the command succeeded but wrote no file at the requested path")
    check = None if case.export_check is None else case.export_check(plan, output)
    return export_stage(exported, check)


def _scope(case: Case, plan: RowPlan) -> ReturnScope:
    return ReturnScope(case.tree, case.report.persona, plan.modelo, plan.year, plan.period)


def run_case(case: Case, selection: Selection) -> CaseSummary:
    """Run the selected returns in chain order and write a line for each wanted one.

    After a return leaves an effect unsettled, no further command is sent: every later wanted return is reported
    as an ``error`` that names where the chain stopped.
    """
    written: list[ReturnKey] = []
    stopped_at: ReturnKey | None = None
    for plan in selection.run:
        if stopped_at is None:
            result = run_return(case, plan)
            stopped_at = plan.key if result.uncertain else None
        else:
            result = RowResult(
                StageResult("error", reason=f"chain stopped after UNKNOWN at {'/'.join(map(str, stopped_at))}")
            )
        if plan.key in selection.wanted and plan.key not in case.done:
            case.writer.write(return_line(_scope(case, plan), result, case.log))
            written.append(plan.key)
    return CaseSummary(tuple(written), stopped_at, selection.skipped)


class _ProfileBound:
    """A runner whose authenticated commands select one exact profile by its label, as the root option does."""

    def __init__(self, runner: Runner, profile: str) -> None:
        self._runner = runner
        self._profile = profile

    def __call__(self, args: Sequence[str], *, authenticated: bool = True) -> Mapping[str, object] | None:
        selected = ("--profile", self._profile, *args) if authenticated else tuple(args)
        return self._runner(selected, authenticated=authenticated)


def bind_profile(runner: Runner, profile: str) -> Runner:
    """``runner`` with every authenticated command aimed at the profile labelled ``profile``.

    A runtime serving one profile still needs the target stated for a command that carries the passphrase.
    """
    return _ProfileBound(runner, profile)


def profile_check(runner: Runner) -> tuple[bool, str, str | None]:
    """Whether the world's profile is the only one the runtime serves and loads: ``(loads, reason, profile name)``.

    The profile list is read without the passphrase; the work list needs it, so a wrong passphrase or an unreadable
    profile shows here before any return is driven.
    """
    listed = classify(runner(("config", "profile", "list"), authenticated=False))
    if listed.kind is not Kind.OK:
        return False, f"config profile list: {listed.reason or listed.kind.value}", None
    rows = listed.result.get("profiles")
    names = [str(row.get("name")) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []
    if len(names) != 1:
        return False, f"the runtime serves {len(names)} profiles; the world holds exactly one", None
    loaded = classify(bind_profile(runner, names[0])((*_WORK, "list")))
    if loaded.kind is not Kind.OK:
        return False, f"app modelo work list: {loaded.reason or loaded.kind.value}", names[0]
    return True, f"profile {names[0]} loaded", names[0]
