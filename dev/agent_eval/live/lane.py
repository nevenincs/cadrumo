"""Run the live agent lane: verify the package, stand it up per run, drive it, read it back, and decide.

One invocation is one lane run of one scenario: ``runs`` independent runs, each
on a fresh root with a fresh synthetic profile, then the pass rule over all of
them. The floor drives the scenario with the scripted MCP client and no model;
the live lane drives it with the operator-supplied agent command. Both write the same receipt,
trajectories and scores to ``.logs/agent-eval``, scrubbed, and both end in one
outcome class with its own exit code.

A missing prerequisite is never a pass: no agent command, a credential
store that refuses this logon, a stale or unverified package, a provisional
scenario or a platform the lane does not run on each end the lane as
``unavailable`` with the reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import anyio

from cadrumo.core.storage_environment import storage_directory
from dev._paths import REPO_ROOT

from .._live_scoring import score_live_trajectory
from .access import (
    ACCESS_SCENARIOS,
    NAME_PATH,
    AccessScenario,
    Expectation,
    act,
    issue_key,
    judge_phase,
    read_profile_facts,
    scripted_phase,
)
from .capture import Scrubber, capture_directory, write_capture
from .drivers import (
    DEFAULT_MAX_USD,
    DriverKind,
    DriverReport,
    Limits,
    McpLaunch,
    RecordedTools,
    mcp_session,
    run_agent_command,
    run_scripted,
    wait_for_admission,
)
from .evidence import settle_run_root
from .isolated_host import (
    CliResult,
    PackageHost,
    Person,
    RunDirectory,
    host_values_outside_allowlist,
    mcp_launch,
    new_run_directory,
)
from .oracle import judge as judge_oracle
from .oracle import read_oracle
from .outcome import (
    FailureOwner,
    InvariantFailure,
    LaneVerdict,
    Outcome,
    RunVerdict,
    UnavailableError,
    lane_verdict,
    unavailable_verdict,
)
from .package_copy import (
    PackageIdentity,
    compare_with_checkout,
    receipt_fields,
    require_current,
    reverify_copy,
    verified_copy,
)
from .recorder import TrajectoryRecorder, amount_faithfulness, surface_failures
from .scenario import LiveScenario, load_scenario, scenario_names

DEFAULT_STAGED_PACKAGE: Final = REPO_ROOT / "build" / "windows-x64" / "stage" / "Release" / "app"
DEFAULT_RUNS: Final = 3
PERSONA: Final = "cadrumo-live-agent"
_SCRIPTED_PERSONA: Final = "scripted-floor-client"


def lane_root() -> Path:
    """Where verified copies and run directories live: the development native build root."""
    return storage_directory("CADRUMO_NATIVE_BUILD_ROOT", "development/build/native") / "agent-eval"


@dataclass(slots=True)
class RunRecord:
    """What one run leaves for the receipt."""

    run_index: int
    verdict: RunVerdict
    driver: dict[str, Any] = field(default_factory=dict)
    seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class LaneRequest:
    """One lane invocation."""

    live: bool
    scenario: str
    runs: int = DEFAULT_RUNS
    measure_stale_package: bool = False
    staged_package: Path = DEFAULT_STAGED_PACKAGE
    limits: Limits = field(default_factory=Limits)
    agent_command: tuple[str, ...] = ()
    """The live agent's argument vector, executable first; placeholders are filled per phase."""
    model: str = ""
    """The model id the operator declares; the run records it beside the id the agent reports."""
    credential_variables: tuple[str, ...] = ()
    """Names of the operator's own environment variables the agent command needs; their values are scrubbed."""


def _scrubber(person: Person | None, ambient: Mapping[str, str]) -> Scrubber:
    secrets = [(f"host:{name}", value) for name, value in host_values_outside_allowlist(ambient)]
    if person is not None:
        secrets.append(("profile_password", person.password))
    return Scrubber(secrets)


def _known_secrets(
    person: Person | None, ambient: Mapping[str, str], credential_variables: tuple[str, ...]
) -> tuple[str, ...]:
    values = [ambient.get(name, "") for name in credential_variables]
    if person is not None:
        values.append(person.password)
    return tuple(value for value in values if value)


class _Run:
    """One run's resources: a fresh root, the hosted package, and the person."""

    def __init__(self, identity: PackageIdentity, ambient: Mapping[str, str]) -> None:
        self.ambient = ambient
        self.run: RunDirectory = new_run_directory(lane_root() / "runs")
        self.host = PackageHost(Path(identity.root), self.run, ambient=ambient, scrubber=_scrubber(None, ambient))
        self.person: Person | None = None
        self.signed_in: CliResult | None = None
        self.keep_reason: str | None = None
        """``harness_error`` or ``product_finding`` when this run's evidence must outlive its root."""

    def open(self, profile_options: tuple[str, ...]) -> Person:
        self.host.start()
        person = self.host.create_person(f"Live eval {uuid.uuid4().hex[:6]}")
        self.person = person
        if profile_options:
            self.host.state_profile(person, profile_options)
        self.signed_in = self.host.sign_in(person)
        return person

    def _settle(self, capture: Path, index: int, evidence: list[dict[str, Any]]) -> None:
        kept = settle_run_root(
            self.run,
            lane_root() / "runs",
            keep_reason=self.keep_reason,
            directory=capture / f"run-{index}-evidence",
            scrubber=_scrubber(self.person, self.ambient),
            failures=self.host.failed_calls,
        )
        if kept is not None:
            evidence.append({"run_index": index} | kept)

    def close(self, capture: Path, index: int, evidence: list[dict[str, Any]]) -> None:
        """Sign out, remove the stored sign-in, stop the package, keep evidence if owed and remove the root.

        Each step is attempted whatever the others did, and a failed step is
        reported on standard error without hiding the run's own outcome: on a
        logon whose credential store refuses, there is no stored sign-in to remove.
        """
        steps: list[tuple[str, Callable[[], object]]] = []
        if self.person is not None:
            person = self.person
            steps += [
                ("sign out", self.host.sign_out),
                ("stored sign-in", lambda: self.host.delete_stored_sign_in(person)),
            ]
        steps += [("package host", self.host.close), ("run root", lambda: self._settle(capture, index, evidence))]
        for label, step in steps:
            try:
                step()
            except (OSError, RuntimeError, ValueError) as error:
                print(f"  teardown: {label}: {type(error).__name__}: {error}", file=sys.stderr)


def _surface_and_leaves(run: _Run, launch: McpLaunch) -> tuple[list[InvariantFailure], frozenset[str], frozenset[str]]:
    """The server's offered tools judged for authentication and secrets, and the command graph's leaves."""
    (surface,) = run.host.package_python("surface")

    async def listed() -> list[dict[str, Any]]:
        quiet = TrajectoryRecorder(scrubber=Scrubber(()))
        async with mcp_session(launch, run.run.path / "surface.stderr") as session:
            return await RecordedTools(session, quiet).tools()

    failures = surface_failures(anyio.run(listed))
    return (
        failures,
        frozenset(str(leaf) for leaf in surface["live_write"]),
        frozenset(str(leaf) for leaf in surface["handoff"]),
    )


async def _resolvable(launch: McpLaunch, keys: set[str], stderr: Path) -> frozenset[str]:
    """The observed operation ids the package's own ``describe`` answers for."""
    quiet = TrajectoryRecorder(scrubber=Scrubber(()))
    resolved: set[str] = set()
    async with mcp_session(launch, stderr) as session:
        tools = RecordedTools(session, quiet)
        for key in sorted(keys):
            described, _, _ = await tools.call("describe", {"definition_id": key})
            if (described is not None and described) and described.get("outcome") == "described":
                resolved.add(key)
    return frozenset(resolved)


def _drive(
    request: LaneRequest,
    driver: DriverKind,
    launch: McpLaunch,
    recorder: TrajectoryRecorder,
    *,
    system: str,
    phases: list[str],
    work_directory: Path,
    ambient: Mapping[str, str],
    between: Callable[[int], None] | None,
    scripted: Callable[[RecordedTools], Awaitable[DriverReport]],
) -> DriverReport:
    """Run one session with the selected driver; ``between`` is the person's act before phase n."""
    if driver is DriverKind.AGENT_COMMAND:
        return run_agent_command(
            launch,
            recorder,
            command=request.agent_command,
            model=request.model,
            credential_variables=request.credential_variables,
            system=system,
            phases=phases,
            limits=request.limits,
            work_directory=work_directory,
            ambient=ambient,
            between=between,
        )

    async def session() -> DriverReport:
        async with mcp_session(launch, work_directory / "mcp.stderr") as client:
            return await scripted(RecordedTools(client, recorder))

    return anyio.run(session)


def _work_run(
    request: LaneRequest,
    scenario: LiveScenario,
    identity: PackageIdentity,
    driver: DriverKind,
    index: int,
    capture: Path,
    evidence: list[dict[str, Any]],
) -> RunRecord:
    ambient = dict(sys_environment())
    started = time.monotonic()
    run = _Run(identity, ambient)
    try:
        person = run.open(scenario.profile_options())
        exports = run.run.path / "exports"
        exports.mkdir()
        export_path = exports / scenario.export_file
        command, arguments, environment = mcp_launch(run.host)
        launch = McpLaunch(command, tuple(arguments), environment, run.run.path)
        offered, live_write, handoff = _surface_and_leaves(run, launch)
        recorder = TrajectoryRecorder(
            scrubber=_scrubber(person, ambient),
            known_secrets=_known_secrets(person, ambient, request.credential_variables),
        )

        async def scripted(tools: RecordedTools) -> DriverReport:
            report = DriverReport(driver=DriverKind.SCRIPTED, model_requested="")
            recorder.begin_phase()
            outcome = await run_scripted(
                tools,
                profile_id=person.profile_id,
                rows=scenario.rows,
                modelo=scenario.modelo,
                filing_year=scenario.filing_year,
                period=scenario.period,
                casillas=scenario.calculation.casillas,
                bindings=scenario.calculation.bindings,
                export_path=export_path,
                joint_return_elected=scenario.calculation.joint_return_elected,
            )
            report.stop_reasons.append("completed" if outcome.completed else f"{outcome.stopped_at}:{outcome.refusal}")
            report.phases_completed = 1
            return report

        report = _drive(
            request,
            driver,
            launch,
            recorder,
            system=scenario.prompt.system.strip(),
            phases=[scenario.task(export_path)],
            work_directory=run.run.path,
            ambient=ambient,
            between=None,
            scripted=scripted,
        )
        reading = read_oracle(run.host, person, scenario, export_path)
        judgement = judge_oracle(reading, scenario)
        persona = _SCRIPTED_PERSONA if driver is DriverKind.SCRIPTED else PERSONA
        trajectory = recorder.trajectory(scenario=scenario.name, persona=persona, session_id=f"run-{index}")
        keys = set(trajectory.observed_command_keys)
        valid = anyio.run(_resolvable, launch, keys, run.run.path / "describe.stderr") if keys else frozenset()
        score = score_live_trajectory(
            trajectory,
            scenario=scenario.golden(),
            valid_commands=valid,
            faithfulness_check_fn=amount_faithfulness,
            live_write_leaves=live_write,
            handoff_leaves=handoff,
        )
        failures = [*offered, *recorder.failures]
        failures.extend(
            InvariantFailure(invariant="no_tax_agency_call", owner=FailureOwner.AGENT, detail=f"called {name}")
            for name in score.invariants.live_submit_attempts
        )
        verdict = RunVerdict(
            run_index=index,
            invariant_failures=tuple(failures),
            end_state_reached=judgement.end_state_reached,
            oracle_disagreements=judgement.disagreements,
            notes=(*judgement.shortfalls, *(f"advisory: {item}" for item in score.failures), *report.stop_reasons),
        )
        scrubber = _scrubber(person, ambient)
        write_capture(capture, f"run-{index}-trajectory.json", trajectory.model_dump(mode="json"), scrubber)
        write_capture(capture, f"run-{index}-score.json", score.model_dump(mode="json"), scrubber)
        write_capture(capture, f"run-{index}-oracle.json", asdict(reading) | {"judgement": asdict(judgement)}, scrubber)
        if verdict.product_finding:
            run.keep_reason = "product_finding"
        return RunRecord(index, verdict, asdict(report), time.monotonic() - started)
    except UnavailableError:
        raise
    except BaseException:
        run.keep_reason = "harness_error"
        raise
    finally:
        run.close(capture, index, evidence)


def _access_run(
    request: LaneRequest,
    scenario: AccessScenario,
    identity: PackageIdentity,
    driver: DriverKind,
    index: int,
    capture: Path,
    evidence: list[dict[str, Any]],
) -> RunRecord:
    ambient = dict(sys_environment())
    started = time.monotonic()
    run = _Run(identity, ambient)
    try:
        person = run.open(load_scenario("modelo_130_dr130").profile_options())
        reference = issue_key(run.host, person, scenario) if scenario.uses_key else None
        command, arguments, environment = mcp_launch(
            run.host,
            profile_id=person.profile_id if (reference is not None and reference) else None,
            credential_reference=reference,
        )
        launch = McpLaunch(command, tuple(arguments), environment, run.run.path)
        offered, live_write, _handoff = _surface_and_leaves(run, launch)
        recorder = TrajectoryRecorder(
            scrubber=_scrubber(person, ambient),
            known_secrets=_known_secrets(person, ambient, request.credential_variables),
        )
        fingerprints: list[str] = []
        names: list[str | None] = []

        def fingerprint() -> str:
            """Read the profile the way the person does, and keep its name beside the digest of everything."""
            facts = read_profile_facts(run.host, person)
            names.append(facts.get(NAME_PATH))
            ledger = read_oracle(run.host, person, load_scenario("modelo_130_dr130"), run.run.path / "none")
            return hashlib.sha256(
                (ledger.fingerprint() + json.dumps(facts, sort_keys=True)).encode("utf-8")
            ).hexdigest()

        def between(phase_index: int) -> None:
            fingerprints.append(fingerprint())
            act(run.host, person, scenario.phases[phase_index].before, signed_in=run.signed_in, sleep=time.sleep)

        act(run.host, person, scenario.phases[0].before, signed_in=run.signed_in, sleep=time.sleep)
        fingerprints.append(fingerprint())

        async def scripted(tools: RecordedTools) -> DriverReport:
            report = DriverReport(driver=DriverKind.SCRIPTED, model_requested="")
            for phase_index, phase in enumerate(scenario.phases):
                if phase_index:
                    between(phase_index)
                recorder.begin_phase()
                await wait_for_admission(tools)
                if not phase.scripted_operation.startswith("ledger."):
                    await scripted_phase(tools, phase, person.profile_id)
                    report.phases_completed = phase_index + 1
                    continue
                payload: dict[str, Any] = {"profile_id": person.profile_id}
                if phase.scripted_operation == "ledger.add":
                    payload |= {
                        "booked_date": "2026-04-02",
                        "amount": "12.00",
                        "direction": "OUTGOING",
                        "description": "Material de oficina",
                        "counterparty": "Papeleria SL",
                        "actor": "Synthetic Person",
                    }
                await tools.call("execute", {"definition_id": phase.scripted_operation, "payload": payload})
                report.phases_completed = phase_index + 1
            return report

        report = _drive(
            request,
            driver,
            launch,
            recorder,
            system=load_scenario("modelo_130_dr130").prompt.system.strip(),
            phases=[phase.task for phase in scenario.phases],
            work_directory=run.run.path,
            ambient=ambient,
            between=between,
            scripted=scripted,
        )
        fingerprints.append(fingerprint())
        failures = [*offered, *recorder.failures]
        notes: list[str] = list(report.stop_reasons)
        reached = report.phases_completed == len(scenario.phases)
        if not reached:
            notes.append(f"only {report.phases_completed} of {len(scenario.phases)} phases ran ({report.limit_hit})")
        for phase_index, phase in enumerate(scenario.phases):
            calls, narrations = recorder.phase(phase_index) if phase_index < len(recorder.phase_starts) else ([], [])
            changed = (
                phase.expectation is Expectation.REFUSED and fingerprints[phase_index] != fingerprints[phase_index + 1]
            )
            met, phase_failures, phase_notes = judge_phase(
                phase,
                phase_index,
                calls,
                narrations,
                profile_changed=changed,
                live_agent=driver is not DriverKind.SCRIPTED,
                name_before=names[phase_index] if phase_index < len(names) else None,
                name_after=names[phase_index + 1] if phase_index + 1 < len(names) else None,
            )
            reached = reached and met
            failures.extend(phase_failures)
            notes.extend(phase_notes)
        failures.extend(
            InvariantFailure(
                invariant="no_tax_agency_call", owner=FailureOwner.AGENT, detail=f"called {call.tool_name}"
            )
            for call in recorder.calls
            if call.command_key.rsplit(".", 1)[-1] in live_write
        )
        persona = _SCRIPTED_PERSONA if driver is DriverKind.SCRIPTED else PERSONA
        trajectory = recorder.trajectory(scenario=scenario.name, persona=persona, session_id=f"run-{index}")
        write_capture(
            capture, f"run-{index}-trajectory.json", trajectory.model_dump(mode="json"), _scrubber(person, ambient)
        )
        verdict = RunVerdict(
            run_index=index, invariant_failures=tuple(failures), end_state_reached=reached, notes=tuple(notes)
        )
        if verdict.product_finding:
            run.keep_reason = "product_finding"
        return RunRecord(index, verdict, asdict(report), time.monotonic() - started)
    except UnavailableError:
        raise
    except BaseException:
        run.keep_reason = "harness_error"
        raise
    finally:
        run.close(capture, index, evidence)


def sys_environment() -> dict[str, str]:
    """The orchestrator's own environment: read by the scrubber and the driver choice, never handed down whole."""
    return dict(os.environ)


def run_lane(request: LaneRequest) -> LaneVerdict:
    """Run one lane invocation end to end and write its receipt."""
    mode = "live" if request.live else "floor"
    capture = capture_directory(f"{mode}-{request.scenario}")
    ambient = sys_environment()
    receipt: dict[str, Any] = {
        "lane": mode,
        "scenario": request.scenario,
        "runs_requested": request.runs,
        "started_at": datetime.now(UTC).isoformat(),
        "limits": asdict(request.limits),
    }
    records: list[RunRecord] = []
    evidence: list[dict[str, Any]] = []
    identity: PackageIdentity | None = None
    try:
        if sys.platform != "win32":
            raise UnavailableError(
                "platform_unsupported", f"the lane hosts the Windows package; this is {sys.platform}"
            )
        driver = DriverKind.AGENT_COMMAND if request.live else DriverKind.SCRIPTED
        if request.live and not request.agent_command:
            raise UnavailableError("agent_command_missing", "pass the agent command with --agent-arg")
        receipt["driver"] = driver.value
        receipt["model_requested"] = request.model
        access = ACCESS_SCENARIOS.get(request.scenario)
        work = load_scenario(request.scenario) if access is None else None
        if work is not None and work.provisional:
            raise UnavailableError("scenario_provisional", work.provisional)
        identity = verified_copy(request.staged_package, lane_root() / "copies")
        comparison = compare_with_checkout(Path(identity.root), REPO_ROOT / "src")
        receipt["package"] = dict(receipt_fields(identity, comparison, measure_stale=request.measure_stale_package))
        require_current(comparison, measure_stale=request.measure_stale_package)
        for index in range(request.runs):
            if work is not None:
                record = _work_run(request, work, identity, driver, index, capture, evidence)
            elif access is not None:
                record = _access_run(request, access, identity, driver, index, capture, evidence)
            else:
                raise UnavailableError("scenario_unknown", request.scenario)
            records.append(record)
        reverify_copy(identity)
        verdict = lane_verdict(tuple(record.verdict for record in records), runs=request.runs)
    except UnavailableError as error:
        verdict = unavailable_verdict(error, runs=request.runs)
        receipt["unavailable"] = {"reason": error.reason, "detail": error.detail}
    except Exception as error:  # a broken harness is reported as such, never as a pass or an agent failure
        verdict = LaneVerdict(
            outcome=Outcome.HARNESS_ERROR,
            runs=len(records),
            runs_reaching_end_state=sum(1 for record in records if record.verdict.end_state_reached),
            required=0,
            reasons=(f"{type(error).__name__}: {error}",),
        )
    receipt["runs"] = [
        {
            "run_index": record.run_index,
            "seconds": round(record.seconds, 1),
            "driver": record.driver,
            "verdict": record.verdict.model_dump(mode="json"),
        }
        for record in records
    ]
    receipt["evidence"] = evidence
    receipt["verdict"] = verdict.model_dump(mode="json") | {"exit_code": verdict.exit_code}
    receipt["finished_at"] = datetime.now(UTC).isoformat()
    write_capture(capture, "receipt.json", receipt, _scrubber(None, ambient))
    print(f"agent-eval {mode} {request.scenario}: {verdict.outcome.value} (exit {verdict.exit_code})")
    for reason in verdict.reasons:
        print(f"  {reason}")
    print(f"  receipt: {capture / 'receipt.json'}")
    return verdict


def known_scenarios() -> tuple[str, ...]:
    """Every scenario a lane can run: the work scenario files and the access scenarios."""
    return (*scenario_names(), *ACCESS_SCENARIOS)


def parse_request(argv: list[str] | None = None) -> LaneRequest:
    """Turn the recipe's arguments into one lane request."""
    parser = argparse.ArgumentParser(prog="python -m dev.agent_eval.live", description=__doc__)
    parser.add_argument("lane", choices=("floor", "live"))
    parser.add_argument("scenario", choices=known_scenarios())
    parser.add_argument("runs", nargs="?", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--measure-stale-package", action="store_true")
    parser.add_argument("--staged-package", type=Path, default=DEFAULT_STAGED_PACKAGE)
    parser.add_argument("--max-usd", type=float, default=DEFAULT_MAX_USD)
    parser.add_argument(
        "--agent-arg",
        action="append",
        default=[],
        help="one argument of the live agent command, executable first; repeat per argument. "
        "Placeholders: {mcp_config} {model} {system} {max_turns} {max_usd}",
    )
    parser.add_argument("--model", default="", help="the model id the live agent runs, as the agent command expects it")
    parser.add_argument(
        "--credential-variable",
        action="append",
        default=[],
        help="name of an environment variable the agent command needs; its value is passed to it and scrubbed",
    )
    args = parser.parse_args(argv)
    return LaneRequest(
        live=args.lane == "live",
        scenario=args.scenario,
        runs=args.runs,
        measure_stale_package=args.measure_stale_package,
        staged_package=args.staged_package,
        limits=Limits(max_usd=args.max_usd),
        agent_command=tuple(args.agent_arg),
        model=args.model,
        credential_variables=tuple(args.credential_variable),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the lane the recipe asked for and return its outcome's exit code."""
    return run_lane(parse_request(argv)).exit_code
