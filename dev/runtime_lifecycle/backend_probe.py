"""Probe a built package's backend the way the desktop drives it after sign-in, without a window.

The desktop's backend calls, made against a disposable synthetic profile:

1. ``cadrumo-runtime --configured-root`` on a fresh marked development root;
2. profile creation and password sign-in through ``aeat``'s secret channel;
3. ``cadrumo-runtime config sign-in-status`` and ``config activity``, the
   helpers the desktop polls and reports activity through;
4. ``cadrumo-runtime session hold``, its ``status`` and two ``activity``
   requests far enough apart to take the session renewal branch, while the
   runtime must stay alive;
5. the agent service started and admitted as the desktop does, on a second
   fresh root, through :func:`agent_service_session`.

Every step is recorded with its outcome; a failed step does not hide the ones
after it unless they depend on it. The run then prints the warning and error
records its own roots logged. Exit 0 means every step held, 1 that one failed.
Run it with ``uv run --no-sync python -m dev.runtime_lifecycle.backend_probe
--package build/windows-x64/stage/Debug/app``. ``--source`` runs the same calls
through this checkout's environment instead, under the runtime's explicit
development session admission, so a Python change needs no package rebuild.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cadrumo.core.errors.failure_report import failure_chain
from cadrumo_runtime.application.development_root import mark_development_root
from dev._paths import REPO_ROOT

from .agent_service_session import agent_service_session
from .caller_owned_root import AcceptanceError, Programs, caller_owned_runtime, consumer_environment, require
from .proof_support import create_profile, identify_profile, login_profile
from .session_holder import WindowsRuntimeSessionHolder

_COMMAND_SECONDS = 120
# The runtime renews sibling human leases only after this much quiet time.
_RENEWAL_SECONDS = 16.0
# A runtime stopping after a fatal handler error is still a live process for a moment.
_EXIT_SETTLE_SECONDS = 3.0
_LOG_LINES = 60
_DEVELOPMENT_SESSION = {"CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE": "1"}


@dataclass(slots=True)
class Probe:
    """The recorded outcome of every step, printed as it happens."""

    steps: list[dict[str, Any]] = field(default_factory=list)

    def step(self, name: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any] | None:
        """Run one step, record its facts or its failure, and return the facts."""
        started = time.monotonic()
        entry: dict[str, object]
        try:
            facts = action()
        except Exception as error:
            frame = traceback.extract_tb(error.__traceback__)[-1]
            entry = {
                "step": name,
                "ok": False,
                "error": f"{type(error).__name__}: {error}",
                "raised_at": f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}",
                "error_chain": " <- ".join(link.render() for link in failure_chain(error)),
            }
            facts = None
        else:
            entry = {"step": name, "ok": True, **facts}
        entry["seconds"] = round(time.monotonic() - started, 2)
        self.steps.append(entry)
        print(json.dumps(entry, sort_keys=True, default=str), flush=True)
        return facts

    @property
    def failed(self) -> bool:
        """Whether any recorded step failed."""
        return any(not entry["ok"] for entry in self.steps)


def runtime_command(programs: Programs, environment: Mapping[str, str], *words: str) -> dict[str, Any]:
    """Run one runtime CLI helper exactly as the desktop does and return its envelope facts."""
    result = subprocess.run(  # noqa: S603 -- exact packaged executable; no shell; no secret.
        [str(programs.runtime), "--format", "json", "config", *words],
        input="",
        env=dict(environment),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=_COMMAND_SECONDS,
        check=False,
    )
    text = result.stdout.strip() or result.stderr.strip()
    try:
        envelope = json.loads(text.splitlines()[-1] if text else "{}")
    except ValueError:
        envelope = {}
    error = envelope.get("error") if isinstance(envelope, dict) else None
    facts: dict[str, Any] = {"exit": result.returncode, "status": envelope.get("status")}
    if isinstance(error, dict):
        facts.update(code=error.get("code"), context=error.get("context"), trace_id=error.get("trace_id"))
    require(result.returncode == 0, json.dumps(facts, default=str))
    return facts


def holder_request(holder: WindowsRuntimeSessionHolder, action: str) -> dict[str, Any]:
    """Send one held-session request and require an answer other than a refusal."""
    reply = holder.command(action)
    require(reply.get("kind") != "session_refused", f"{action} refused: {reply.get('code')}")
    return {"kind": reply.get("kind")}


def runtime_alive(runtime: Any) -> dict[str, Any]:
    """Require the caller-owned runtime process to still be running once a fatal stop would have settled."""
    try:
        code = runtime.process.wait(timeout=_EXIT_SETTLE_SECONDS)
    except subprocess.TimeoutExpired:
        return {"pid": runtime.process.pid}
    raise AcceptanceError(f"runtime exited with {code}")


def source_programs() -> Programs:
    """This checkout's entry points, the source counterparts of a package's ``bin``."""
    scripts = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    suffix = ".exe" if sys.platform == "win32" else ""
    names = ("aeat", "cadrumo-runtime", "cadrumo-mcp")
    return Programs(*((scripts / f"{name}{suffix}").resolve(strict=True) for name in names))


def signed_in_phase(probe: Probe, programs: Programs, scratch: Path, *, source: bool) -> None:
    """Sign in on a fresh root and make the desktop's post-sign-in calls."""
    root, secrets = scratch / "storage", scratch / "secrets"
    root.mkdir(parents=True)
    secrets.mkdir(parents=True)
    environment = consumer_environment(root, secrets)
    if source:
        # A package carries its own published authority; a checkout uses the one the justfile pins.
        environment.update(_DEVELOPMENT_SESSION, CADRUMO_AUTHORITY_ROOT=str(REPO_ROOT / ".authority"))
    mark_development_root(root)
    with ExitStack() as cleanup:
        runtime = cleanup.enter_context(caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log"))
        if probe.step("runtime_ready", lambda: {"kind": runtime.ready().get("kind")}) is None:
            return
        created = probe.step("profile_create", lambda: {"profile": create_profile(programs, environment, "probe")})
        if created is None:
            return
        profile = created.pop("profile")
        if probe.step("profile_login", lambda: {"persisted": login_profile(programs, environment, profile)}) is None:
            return
        identified = probe.step(
            "profile_identify", lambda: {"profile": identify_profile(programs, environment, profile)}
        )
        if identified is None:
            return
        profile = identified.pop("profile")
        probe.step("sign_in_status", lambda: runtime_command(programs, environment, "sign-in-status"))
        probe.step("activity_helper", lambda: runtime_command(programs, environment, "activity"))
        probe.step("runtime_alive_after_activity", lambda: runtime_alive(runtime))
        holder = None

        def hold() -> dict[str, Any]:
            nonlocal holder
            if profile.profile_id is None:
                raise AcceptanceError("profile has no verified identity")
            holder = WindowsRuntimeSessionHolder(
                programs.runtime,
                profile_id=profile.profile_id,
                environment=environment,
                password=bytearray(profile.password, "utf-8"),
                frontend="cli",
            )
            cleanup.callback(holder.close)
            return {"kind": holder.identity.get("kind")}

        if probe.step("session_hold", hold) is None or holder is None:
            return
        held = holder
        probe.step("hold_status", lambda: holder_request(held, "status"))
        probe.step("hold_activity", lambda: holder_request(held, "activity"))
        time.sleep(_RENEWAL_SECONDS)
        probe.step("hold_activity_renewal", lambda: holder_request(held, "activity"))
        probe.step("activity_helper_renewal", lambda: runtime_command(programs, environment, "activity"))
        probe.step("runtime_alive_after_renewal", lambda: runtime_alive(runtime))
        probe.step("hold_close", lambda: holder_request(held, "close"))
    probe.step("runtime_stop", lambda: {"exit": runtime.exit_code})


def agent_phase(probe: Probe, package: Path, scratch: Path) -> None:
    """Start and admit the agent service as the desktop does, on its own fresh root."""

    def start() -> dict[str, Any]:
        with agent_service_session(package, scratch) as session:
            event = session.agent_event
            return {"event": event.get("event"), "code": event.get("code"), "timings": session.timings}

    probe.step("agent_service", start)


def logged_problems(scratch: Path) -> list[str]:
    """Return the warning and error records this run's roots logged."""
    lines: list[str] = []
    for path in sorted(scratch.rglob("*")):
        if not path.is_file() or path.suffix not in {".log", ".jsonl"}:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(marker in line for marker in ("[WARNING]", "[ERROR]", "[CRITICAL]", '"failure":{', "Traceback")):
                lines.append(f"{path.relative_to(scratch)}: {line[:400]}")
    return lines[-_LOG_LINES:]


def main(arguments: list[str] | None = None) -> int:
    """Run the probe and print its steps, then the logged problems."""
    parser = argparse.ArgumentParser(prog="backend-probe", description=__doc__.splitlines()[0])
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--package", type=Path, help="A built package, such as stage/<config>/app.")
    selection.add_argument("--source", action="store_true", help="This checkout's environment; no agent phase.")
    parser.add_argument("--skip-agent", action="store_true", help="Probe sign-in and activity only.")
    options = parser.parse_args(arguments)
    base = REPO_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="cadrumo-probe-", dir=base))
    probe = Probe()
    if options.source:
        signed_in_phase(probe, source_programs(), scratch / "signed-in", source=True)
    else:
        package = options.package.resolve(strict=True)
        signed_in_phase(probe, Programs.of(package), scratch / "signed-in", source=False)
        if not options.skip_agent:
            agent_phase(probe, package, scratch / "agent")
    problems = logged_problems(scratch)
    print(json.dumps({"logged_problems": len(problems), "root": str(scratch)}), flush=True)
    for line in problems:
        print(line, flush=True)
    print(json.dumps({"passed": not probe.failed, "failed_steps": [s["step"] for s in probe.steps if not s["ok"]]}))
    return 1 if probe.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
