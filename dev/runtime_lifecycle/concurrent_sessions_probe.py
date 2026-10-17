"""Probe concurrent sign-in, use and sign-out across every frontend on one runtime, without a window.

One caller-owned runtime on a fresh marked root holds two synthetic profiles,
A and B. Each phase starts its actors at once and records every outcome:

1. fan-in: two ``aeat config login A``, a desktop and two CLI session holders
   for A signing in together, then two TUI clients resuming A's sign-in and an
   MCP relay the desktop holder attends; every one must be admitted, and every
   holder must answer ``status`` and ``activity`` concurrently;
2. partial sign-out: one holder closes while the others report activity and a
   new holder signs in; the rest must stay signed in;
3. cross-profile: ``aeat config login B`` while A's holders report activity and
   a TUI client polls; B must be admitted and every A session retired;
4. race: A and B sign in at once through the CLI and through holders; once it
   settles, the live sessions must all belong to one profile;
5. sign-out: ``aeat config logout`` while the remaining holders report
   activity; every holder must be retired;
6. resume race: ``aeat config login B`` while CLI reads of A resume A's saved
   sign-in on their own; afterwards B must still be signed in and A not, since
   an automatic resume never signs another profile out.

The runtime must survive every phase, and the run fails on any error record
its root logged. Run it with ``uv run --no-sync python -m
dev.runtime_lifecycle.concurrent_sessions_probe --source`` or ``--package
build/windows-x64/stage/Debug/app``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import psutil

from cadrumo_runtime.application.development_root import mark_development_root
from dev._paths import REPO_ROOT

from .backend_probe import logged_problems, runtime_alive, source_programs
from .caller_owned_root import (
    AcceptanceError,
    Programs,
    caller_owned_runtime,
    consumer_environment,
    error_code,
    require,
    run_cli,
)
from .mcp_proof_support import execute, mcp_session, settled
from .proof_support import Profile, create_profile
from .session_holder import AsyncRuntimeSessionHolder

_DEVELOPMENT_SESSION = {"CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE": "1"}
_TUI_SECONDS = 20.0
_RETIREMENT_SECONDS = 15.0
_RACE_SETTLE_SECONDS = 8.0
_PROCESS_SECONDS = 180

# The production TUI client calls without mounting Textual: resume the person's
# sign-in, read the protected overview, then report activity and status.
_TUI_CLIENT = """
import asyncio, json, sys, time
from uuid import UUID

import psutil
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core.external_constants import OutputLanguage
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_runtime.host.frontend.tui.profile.overview_client import read_profile_overview
REFUSALS = (FrontendRefusedError, RefusalError, ProfileReceiptRefusedError)
def emit(**document):
    print(json.dumps(document), flush=True)
def code(error):
    reason = getattr(error, 'reason', None)
    return str(getattr(reason, 'value', reason) or type(error).__name__)
async def main():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.TUI)
    try:
        try:
            await asyncio.to_thread(client.resume_receipt)
            view = await asyncio.to_thread(
                read_profile_overview, client, profile_label='Probe', output_language=OutputLanguage.EN
            )
        except REFUSALS as error:
            emit(event='refused', code=code(error))
            return 2
        emit(event='admitted', sections=len(view.sections))
        deadline = time.monotonic() + float(sys.argv[2])
        while time.monotonic() < deadline:
            try:
                await asyncio.to_thread(client.note_activity)
                status = (await asyncio.to_thread(client.status)).status
            except REFUSALS as error:
                emit(event='refused', code=code(error))
                return 3
            denial = None if status.denial is None else str(status.denial.value)
            emit(event='status', denial=denial, own=status.session_id == client.session_id)
            if denial is not None or status.session_id != client.session_id:
                return 4
            await asyncio.sleep(1)
        return 0
    finally:
        await asyncio.to_thread(client.close)
with composed_profile_persistence_ports():
    sys.exit(asyncio.run(main()))
"""


@dataclass(slots=True)
class Run:
    """The recorded checks of one run, printed as they happen."""

    checks: list[dict[str, Any]] = field(default_factory=list)

    def check(self, name: str, ok: bool, **facts: Any) -> bool:
        """Record one expectation and its observed facts."""
        entry = {"check": name, "ok": ok, **facts}
        self.checks.append(entry)
        print(json.dumps(entry, sort_keys=True, default=str), flush=True)
        return ok

    @property
    def failed(self) -> list[str]:
        """Name every check that did not hold."""
        return [entry["check"] for entry in self.checks if not entry["ok"]]


@dataclass(slots=True)
class Context:
    """The programs, environment and profiles one run drives."""

    programs: Programs
    environment: dict[str, str]
    python: list[str]
    scratch: Path
    profiles: dict[str, Profile] = field(default_factory=dict)


@dataclass(slots=True)
class Held:
    """One running session holder and the profile it signed in to."""

    name: str
    profile: str
    holder: AsyncRuntimeSessionHolder


def _describe(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        return "; ".join(_describe(inner) for inner in error.exceptions)
    return f"{type(error).__name__}: {error}"


async def _outcomes(actors: Mapping[str, Awaitable[Any]]) -> dict[str, Any]:
    """Start every actor at once and return each one's result or failure."""
    results = await asyncio.gather(*actors.values(), return_exceptions=True)
    return dict(zip(actors, results, strict=True))


def _profile_ids(context: Context) -> dict[str, UUID]:
    code, document = run_cli(
        context.programs, {**context.environment, "CADRUMO_CLI_REVEAL_IDENTIFIERS": "true"}, "config", "profile", "list"
    )
    require(code == 0, f"profile listing refused: {code} {error_code(document)}")
    rows = (document.get("result") or {}).get("profiles") or []
    return {row["name"]: UUID(row["bucket_id"]) for row in rows if isinstance(row, dict)}


async def cli_login(context: Context, name: str) -> dict[str, Any]:
    """Sign in through ``aeat config login`` and return its exit and error code."""
    profile = context.profiles[name]
    code, envelope = await asyncio.to_thread(
        run_cli,
        context.programs,
        context.environment,
        "config",
        "login",
        profile.name,
        "--secrets-stdin",
        secret={"passphrase": profile.password},
    )
    return {"exit": code, "code": error_code(envelope)}


async def cli_logout(context: Context) -> dict[str, Any]:
    """Sign the active profile out through ``aeat config logout``."""
    code, envelope = await asyncio.to_thread(run_cli, context.programs, context.environment, "config", "logout")
    return {"exit": code, "code": error_code(envelope)}


async def hold(context: Context, name: str, profile: str, frontend: str) -> Held:
    """Sign a desktop or CLI session holder in with the profile's password."""
    record = context.profiles[profile]
    if record.profile_id is None:
        raise AcceptanceError(f"profile {profile} has no identity")
    holder = await AsyncRuntimeSessionHolder.start(
        context.programs.runtime,
        profile_id=record.profile_id,
        environment=context.environment,
        password=bytearray(record.password, "utf-8"),
        frontend="cli" if frontend == "cli" else "desktop",
    )
    return Held(name, profile, holder)


def _ended(holder: AsyncRuntimeSessionHolder) -> str | None:
    """Name how a holder ended: it answers its retirement or refusal and exits, which is the signed-out state."""
    if holder.ended == "session_refused":
        return "refused"
    if holder.ended is not None or holder.exit_code == 0:
        return "retired"
    return None


async def holder_state(held: Held, action: str = "status") -> str:
    """Return ``live`` when the holder's own session answers unrefused, else why not."""
    holder = held.holder
    ended = _ended(holder)
    if ended is not None:
        return ended
    try:
        reply = await holder.command(action)
    except Exception as error:
        return _ended(holder) or f"failed: {_describe(error)}"
    status = reply.get("status") if isinstance(reply.get("status"), dict) else reply
    denial = status.get("denial") if isinstance(status, dict) else None
    own = isinstance(status, dict) and status.get("session_id") == held.holder.identity.get("session_id")
    if action == "status" and (denial is not None or not own):
        return f"not_own:{denial}"
    return "live"


async def tui_client(context: Context, name: str, seconds: float) -> dict[str, Any]:
    """Run the production TUI client calls for ``seconds`` and return its events and exit."""
    record = context.profiles[name]
    process = await asyncio.create_subprocess_exec(
        *context.python,
        "-c",
        _TUI_CLIENT,
        str(record.profile_id),
        str(seconds),
        env=context.environment,
        cwd=context.scratch,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, errors = await asyncio.wait_for(process.communicate(), timeout=_PROCESS_SECONDS)
    events = [json.loads(line) for line in output.decode("utf-8", "replace").splitlines() if line.startswith("{")]
    facts: dict[str, Any] = {"exit": process.returncode, "first": events[:1], "last": events[-1:]}
    if process.returncode not in {0, 2, 3, 4}:
        facts["stderr_tail"] = errors.decode("utf-8", "replace").strip().splitlines()[-3:]
    return facts


async def _approve_relay(holder: AsyncRuntimeSessionHolder, relay_pid: int, call: asyncio.Task[Any]) -> bool:
    """Approve, as the desktop person, the ask the MCP relay process or its descendant made; say whether one came.

    A packaged relay asks as itself; from source the ``cadrumo-mcp`` launcher's
    Python child asks, so the descendants of the started relay count too.
    """
    deadline = time.monotonic() + _PROCESS_SECONDS
    while not call.done() and time.monotonic() < deadline:
        try:
            relay = {relay_pid, *(child.pid for child in psutil.Process(relay_pid).children(recursive=True))}
        except psutil.Error:
            relay = {relay_pid}
        inventory = await holder.command("attendance_inventory")
        for candidate in inventory.get("candidates") or []:
            if isinstance(candidate, dict) and candidate.get("process_id") in relay:
                decided = await holder.command(
                    "attendance_decision", attendance_id=candidate["attendance_id"], approve=True
                )
                require(decided.get("approved") is True, f"attendance decision not applied: {decided.get('kind')}")
                return True
        await asyncio.sleep(0.25)
    return False


async def mcp_read(context: Context, attendant: Held) -> dict[str, Any]:
    """Admit an MCP relay by the desktop person's attendance and run a protected read through it."""
    record = context.profiles[attendant.profile]
    async with mcp_session(
        context.programs, context.environment, context.scratch, stderr=context.scratch / "mcp-stderr.log"
    ) as session:
        # The desktop polls its attendance inventory from sign-in on; the first poll makes it the attendant.
        await attendant.holder.command("attendance_inventory")
        call = asyncio.create_task(session.call("describe", {"definition_id": "auth.local-read"}))
        attended = await _approve_relay(attendant.holder, session.invocation.pid, call)
        is_error, content = await call
        require(attended and not is_error, f"MCP not admitted: attended={attended} {content.get('code')}")
        operation = await execute(session, "auth.local-read", {"profile_id": str(record.profile_id), "kind": "status"})
        result = await settled(session, operation)
        require("error_detail" not in (result.get("document") or {}), f"MCP read not answered: {result.get('code')}")
        return {"attended": True, "answered": True}


async def _all_states(holders: list[Held], action: str) -> dict[str, str]:
    states = await asyncio.gather(*(holder_state(held, action) for held in holders))
    return {held.name: state for held, state in zip(holders, states, strict=True)}


async def _wait_retired(holders: list[Held]) -> dict[str, str]:
    """Poll until every holder is retired or the bound passes; return the last states."""
    deadline = time.monotonic() + _RETIREMENT_SECONDS
    while True:
        states = await _all_states(holders, "status")
        if all(state == "retired" for state in states.values()) or time.monotonic() > deadline:
            return states
        await asyncio.sleep(1)


async def _close(holders: list[Held]) -> None:
    for held in holders:
        try:
            await held.holder.close()
        except Exception as error:
            print(json.dumps({"teardown": held.name, "error": _describe(error)}), flush=True)


def _ok(result: Any) -> bool:
    return not isinstance(result, BaseException) and (not isinstance(result, dict) or result.get("exit") in {0, None})


def _show(result: Any) -> Any:
    if isinstance(result, Held):
        return {"session": result.holder.identity.get("session_id")}
    return _describe(result) if isinstance(result, BaseException) else result


async def phases(run: Run, context: Context, runtime: Any, *, stop_after: str | None = None) -> None:
    """Drive the concurrent phases against one runtime, or those up to `stop_after`."""
    holders: list[Held] = []
    try:
        for name, phase in _PHASES.items():
            await phase(run, context, holders)
            if name == stop_after:
                break
    finally:
        await _close(holders)
    try:
        run.check("runtime_alive_at_end", True, **runtime_alive(runtime))
    except AcceptanceError as error:
        run.check("runtime_alive_at_end", False, error=str(error))


async def _fan_in(run: Run, context: Context, holders: list[Held]) -> None:
    signed_in = asyncio.Event()

    async def login_then_signal() -> dict[str, Any]:
        result = await cli_login(context, "A")
        if result["exit"] == 0:
            signed_in.set()
        return result

    async def tui_after_sign_in(name: str) -> dict[str, Any]:
        await asyncio.wait_for(signed_in.wait(), timeout=_PROCESS_SECONDS)
        return await tui_client(context, "A", 5)

    desktop = asyncio.ensure_future(hold(context, "desktop_A", "A", "desktop"))

    async def mcp_after_desktop() -> dict[str, Any]:
        attendant = await desktop
        await asyncio.wait_for(signed_in.wait(), timeout=_PROCESS_SECONDS)
        return await mcp_read(context, attendant)

    outcomes = await _outcomes(
        {
            "cli_login_A_1": login_then_signal(),
            "cli_login_A_2": login_then_signal(),
            "desktop_A": desktop,
            "cli_hold_A_1": hold(context, "cli_hold_A_1", "A", "cli"),
            "cli_hold_A_2": hold(context, "cli_hold_A_2", "A", "cli"),
            "tui_A_1": tui_after_sign_in("A"),
            "tui_A_2": tui_after_sign_in("A"),
            "mcp_A": mcp_after_desktop(),
        }
    )
    holders.extend(result for result in outcomes.values() if isinstance(result, Held))
    for name, result in outcomes.items():
        admitted = _ok(result) and not (
            isinstance(result, dict) and result.get("first", [{}])[0].get("event") == "refused"
        )
        run.check(f"fan_in.{name}", admitted, outcome=_show(result))
    for action in ("status", "activity"):
        states = await _all_states(holders, action)
        run.check(f"fan_in.concurrent_{action}", all(state == "live" for state in states.values()), states=states)


async def _partial_sign_out(run: Run, context: Context, holders: list[Held]) -> None:
    leaving = next((held for held in holders if held.name == "cli_hold_A_1"), None)
    staying = [held for held in holders if held is not leaving]
    actors: dict[str, Awaitable[Any]] = {
        "new_cli_hold_A_3": hold(context, "cli_hold_A_3", "A", "cli"),
        **{f"activity_{held.name}": holder_state(held, "activity") for held in staying},
    }
    if leaving is not None:
        actors["close_cli_hold_A_1"] = leaving.holder.close()
    outcomes = await _outcomes(actors)
    if leaving is not None:
        holders.remove(leaving)
    joined = outcomes["new_cli_hold_A_3"]
    if isinstance(joined, Held):
        holders.append(joined)
    for name, result in outcomes.items():
        run.check(
            f"partial_sign_out.{name}", isinstance(result, Held) or result in {None, "live"}, outcome=_show(result)
        )
    states = await _all_states(holders, "status")
    run.check(
        "partial_sign_out.others_still_signed_in", all(state == "live" for state in states.values()), states=states
    )


async def mcp_through_handover(
    context: Context, attendant: Held, ready: asyncio.Event, handed_over: asyncio.Event
) -> dict[str, Any]:
    """Hold an attended MCP session across a sign-in to another profile; its reads must then be refused."""
    record = context.profiles[attendant.profile]
    payload = {"profile_id": str(record.profile_id), "kind": "status"}
    async with mcp_session(
        context.programs, context.environment, context.scratch, stderr=context.scratch / "mcp-handover-stderr.log"
    ) as session:
        await attendant.holder.command("attendance_inventory")
        call = asyncio.create_task(session.call("describe", {"definition_id": "auth.local-read"}))
        try:
            attended = await _approve_relay(attendant.holder, session.invocation.pid, call)
            before = await settled(session, await execute(session, "auth.local-read", payload))
        finally:
            ready.set()
        await call
        await asyncio.wait_for(handed_over.wait(), timeout=_PROCESS_SECONDS)
        is_error, after = await session.call(
            "execute", {"definition_id": "auth.local-read", "payload": payload, "start": True}
        )
        return {
            "attended": attended,
            "read_before": "error_detail" not in (before.get("document") or {}),
            "refused_after": is_error,
            "code_after": after.get("code"),
        }


async def _cross_profile(run: Run, context: Context, holders: list[Held]) -> None:
    from_a = [held for held in holders if held.profile == "A"]
    desktop = next((held for held in from_a if held.name == "desktop_A"), None)
    ready, handed_over = asyncio.Event(), asyncio.Event()
    mcp = None
    if desktop is not None:
        mcp = asyncio.ensure_future(mcp_through_handover(context, desktop, ready, handed_over))
        await ready.wait()
    outcomes = await _outcomes(
        {
            "cli_login_B": cli_login(context, "B"),
            "tui_A_polling": tui_client(context, "A", _TUI_SECONDS),
            **{f"activity_{held.name}": holder_state(held, "activity") for held in from_a},
        }
    )
    run.check("cross_profile.cli_login_B", _ok(outcomes["cli_login_B"]), outcome=outcomes["cli_login_B"])
    tui = outcomes["tui_A_polling"]
    run.check(
        "cross_profile.tui_A_signed_out",
        isinstance(tui, dict) and tui.get("exit") in {2, 3, 4},
        outcome=_show(tui),
    )
    states = await _wait_retired(from_a)
    run.check(
        "cross_profile.every_A_holder_retired", all(state == "retired" for state in states.values()), states=states
    )
    handed_over.set()
    if mcp is not None:
        handover = (await _outcomes({"mcp": mcp}))["mcp"]
        run.check(
            "cross_profile.mcp_A_refused_after_handover",
            isinstance(handover, dict)
            and handover["attended"]
            and handover["read_before"]
            and handover["refused_after"],
            outcome=_show(handover),
        )
    for held in from_a:
        holders.remove(held)
        await _close([held])
    joined = await _outcomes(
        {"desktop_B": hold(context, "desktop_B", "B", "desktop"), "cli_hold_B": hold(context, "cli_hold_B", "B", "cli")}
    )
    for name, result in joined.items():
        if isinstance(result, Held):
            holders.append(result)
        run.check(f"cross_profile.{name}", isinstance(result, Held), outcome=_show(result))


async def _race(run: Run, context: Context, holders: list[Held]) -> None:
    outcomes = await _outcomes(
        {
            "cli_login_A": cli_login(context, "A"),
            "cli_login_B": cli_login(context, "B"),
            "race_hold_A": hold(context, "race_hold_A", "A", "cli"),
            "race_hold_B": hold(context, "race_hold_B", "B", "cli"),
            **{f"activity_{held.name}": holder_state(held, "activity") for held in holders},
        }
    )
    holders.extend(result for result in outcomes.values() if isinstance(result, Held))
    run.check(
        "race.every_actor_answered",
        all(
            not isinstance(result, BaseException) or isinstance(result, AcceptanceError) for result in outcomes.values()
        ),
        outcomes={name: _show(result) for name, result in outcomes.items()},
    )
    await asyncio.sleep(_RACE_SETTLE_SECONDS)
    states = await _all_states(holders, "status")
    live_profiles = sorted({held.profile for held in holders if states[held.name] == "live"})
    run.check("race.one_profile_signed_in", len(live_profiles) <= 1, live_profiles=live_profiles, states=states)
    retired = [held for held in holders if states[held.name] != "live"]
    for held in retired:
        holders.remove(held)
    await _close(retired)


async def _sign_out(run: Run, context: Context, holders: list[Held]) -> None:
    outcomes = await _outcomes(
        {
            "cli_logout": cli_logout(context),
            **{f"activity_{held.name}": holder_state(held, "activity") for held in holders},
        }
    )
    run.check("sign_out.cli_logout", _ok(outcomes["cli_logout"]), outcome=outcomes["cli_logout"])
    states = await _wait_retired(holders)
    run.check("sign_out.every_holder_retired", all(state == "retired" for state in states.values()), states=states)


async def cli_profile_view(context: Context, name: str) -> dict[str, Any]:
    """Read a named profile through the CLI, which resumes that profile's saved sign-in on its own."""
    code, envelope = await asyncio.to_thread(
        run_cli, context.programs, context.environment, "config", "profile", "view", context.profiles[name].name
    )
    return {"exit": code, "code": error_code(envelope)}


async def _resume_race(run: Run, context: Context, holders: list[Held]) -> None:
    """Sign in to B while automatic resumes of A run: the resumes must never sign B out."""
    del holders
    first = await cli_login(context, "A")
    run.check("resume_race.cli_login_A", _ok(first), outcome=first)
    outcomes = await _outcomes(
        {
            "cli_login_B": cli_login(context, "B"),
            **{f"cli_resume_A_{index}": cli_profile_view(context, "A") for index in range(3)},
        }
    )
    run.check("resume_race.cli_login_B", _ok(outcomes["cli_login_B"]), outcome=outcomes["cli_login_B"])
    run.check(
        "resume_race.every_resume_answered",
        all(isinstance(result, dict) for result in outcomes.values()),
        outcomes={name: _show(result) for name, result in outcomes.items()},
    )
    after = await _outcomes({"tui_B": tui_client(context, "B", 3), "tui_A": tui_client(context, "A", 3)})
    tui_b, tui_a = after["tui_B"], after["tui_A"]
    run.check("resume_race.B_still_signed_in", isinstance(tui_b, dict) and tui_b.get("exit") == 0, outcome=_show(tui_b))
    run.check(
        "resume_race.A_signed_out", isinstance(tui_a, dict) and tui_a.get("exit") in {2, 3, 4}, outcome=_show(tui_a)
    )
    final = await cli_logout(context)
    run.check("resume_race.cli_logout", _ok(final), outcome=final)


_PHASES: dict[str, Callable[[Run, Context, list[Held]], Awaitable[None]]] = {
    "fan_in": _fan_in,
    "partial_sign_out": _partial_sign_out,
    "cross_profile": _cross_profile,
    "race": _race,
    "sign_out": _sign_out,
    "resume_race": _resume_race,
}


def _setup(run: Run, context: Context) -> bool:
    for name in ("A", "B"):
        try:
            context.profiles[name] = create_profile(context.programs, context.environment, f"probe-{name.lower()}")
        except AcceptanceError as error:
            return run.check(f"setup.create_{name}", False, error=str(error))
    identities = _profile_ids(context)
    for name, profile in list(context.profiles.items()):
        identity = identities.get(profile.name)
        context.profiles[name] = Profile(profile.name, profile.password, identity)
        if not run.check(f"setup.identify_{name}", identity is not None):
            return False
    return True


def main(arguments: list[str] | None = None) -> int:
    """Run the concurrent session probe and print its checks, then the logged problems."""
    parser = argparse.ArgumentParser(prog="concurrent-sessions-probe", description=__doc__.splitlines()[0])
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--package", type=Path, help="A built package, such as stage/<config>/app.")
    selection.add_argument("--source", action="store_true", help="This checkout's environment.")
    parser.add_argument("--stop-after", choices=tuple(_PHASES), help="Run the phases up to this one only.")
    options = parser.parse_args(arguments)
    base = REPO_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="cadrumo-concurrent-", dir=base))
    root, secrets = scratch / "storage", scratch / "secrets"
    root.mkdir()
    secrets.mkdir()
    environment = consumer_environment(root, secrets)
    if options.source:
        programs = source_programs()
        python = [sys.executable]
        environment.update(_DEVELOPMENT_SESSION, CADRUMO_AUTHORITY_ROOT=str(REPO_ROOT / ".authority"))
    else:
        package = options.package.resolve(strict=True)
        programs = Programs.of(package)
        python = [str(package / "python.exe"), "-I"]
    mark_development_root(root)
    context = Context(programs, environment, python, scratch)
    run = Run()
    started = time.monotonic()
    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        if run.check("runtime_ready", runtime.ready().get("kind") is not None) and _setup(run, context):
            asyncio.run(phases(run, context, runtime, stop_after=options.stop_after))
    problems = logged_problems(scratch)
    run.check(
        "no_error_records",
        # A refusal's traceback belongs to its WARNING record; only error records are failures here.
        not any("[ERROR]" in line or "[CRITICAL]" in line for line in problems),
    )
    for line in problems:
        print(line, flush=True)
    print(
        json.dumps(
            {
                "passed": not run.failed,
                "failed": run.failed,
                "seconds": round(time.monotonic() - started, 1),
                "root": str(scratch),
            }
        )
    )
    return 1 if run.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
