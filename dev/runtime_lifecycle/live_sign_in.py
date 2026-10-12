"""Prove the held live sign-in and attended MCP lifecycle through a built package's own programs.

Everything runs as real processes on a fresh storage root: the package's
``cadrumo-runtime --configured-root``, its ``aeat`` command line and its
``cadrumo-mcp`` server, driven by an MCP client. Nothing here imports the
product to reach the runtime, observes the OS on the product's behalf, or
substitutes a credential store. The profile passwords live only in this
process's memory and on the command line's standard input.

The run proves, and records as one receipt line per step:

- the package registers ``config sign-in-hold``;
- with no held sign-in, MCP is refused before any authentication;
- a held sign-in is reported with its deadline, and an MCP connection's ask
  names the kernel-verified process, which descends from this harness;
- a declined ask, and a connection naming another profile, are refused;
- an approved connection is admitted as ``attended`` and reads the
  profile's own known data through a registered operation;
- signing out from the holder, closing the holder's input, a password-proven
  ``config logout`` from another process, a profile-wide lock, the sign-in's
  own deadline, and stopping the runtime each end that access;
- no stored sign-in is written, the person's own Cadrumo data is unchanged,
  and no process this run started survives it.

Run it with ``just verify-live-sign-in PACKAGE``. ``--programs`` points at a
directory of entry points instead, such as a development environment's
scripts, for a quick run that is not package acceptance. ``--skip-expiry``
leaves out the step that waits for the sign-in's own deadline.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import queue
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psutil
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.core.storage_environment import host_installed_default_root

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    Receipt,
    caller_owned_runtime,
    consumer_environment,
    file_facts,
    require,
    run_cli,
)

_PROFILE = "live-sign-in-acceptance"
_OTHER_PROFILE = "live-sign-in-other"
_EVENT_SECONDS = 60
_CALL_SECONDS = 150
_EXPIRY_MARGIN_SECONDS = 45
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Profile:
    """A disposable profile and its password, which never leaves this process except on a CLI's stdin."""

    name: str
    password: str
    profile_id: UUID


class Holder:
    """One ``aeat config sign-in-hold`` process: its event lines, its decisions and its end."""

    def __init__(self, programs: Programs, environment: Mapping[str, str], profile: Profile, log: Path) -> None:
        """Start the holder and give it the password on the first line of its input."""
        self._errors = log.open("ab")
        self.process = subprocess.Popen(  # noqa: S603 -- exact packaged executable; no shell; secret on stdin only.
            [str(programs.aeat), "--format", "json", "config", "sign-in-hold", profile.name],
            env=dict(environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._errors,
        )
        self.lines: queue.Queue[dict[str, Any] | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self._send({"passphrase": profile.password})

    def _read(self) -> None:
        output = self.process.stdout
        if output is None:
            self.lines.put(None)
            return
        for raw in output:
            with suppress(ValueError):
                document = json.loads(raw)
                if isinstance(document, dict):
                    self.lines.put(document)
        self.lines.put(None)

    def _send(self, document: Mapping[str, object]) -> None:
        stdin = self.process.stdin
        if stdin is None or stdin.closed:
            raise AcceptanceError("the holder's input is already closed")
        stdin.write((json.dumps(document) + "\n").encode())
        stdin.flush()

    def event(self, kind: str, *, seconds: float = _EVENT_SECONDS) -> dict[str, Any]:
        """Return the next event of ``kind``, failing on the holder's end or a deadline."""
        deadline = time.monotonic() + seconds
        while True:
            try:
                document = self.lines.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                raise AcceptanceError(f"the holder sent no {kind} event in {seconds:.0f}s") from None
            if document is None:
                raise AcceptanceError(f"the holder ended before a {kind} event (exit {self.process.poll()})")
            if document.get("event") == kind:
                return document

    def decide(self, attendance_id: str, *, approve: bool) -> dict[str, Any]:
        """Answer one exact ask and return the holder's report of the answer."""
        self._send({"approve" if approve else "decline": attendance_id})
        return self.event("attendance_decided")

    def sign_out(self) -> None:
        """Ask the holder to sign the person out."""
        self._send({"sign_out": True})

    def close_input(self) -> None:
        """Close the holder's input, which ends the held sign-in."""
        stdin = self.process.stdin
        if stdin is not None and not stdin.closed:
            stdin.close()

    def finish(self, *, seconds: float = _EVENT_SECONDS) -> tuple[str, int]:
        """Wait for the holder's final ``ended`` event and exit; return the reason and exit code."""
        ended = self.event("ended", seconds=seconds)
        code = self.process.wait(timeout=seconds)
        self._errors.close()
        return str(ended.get("reason")), code

    def stop(self) -> None:
        """End a holder a failed step left running."""
        self.close_input()
        try:
            self.process.wait(timeout=_EVENT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=_EVENT_SECONDS)
        self._errors.close()


@dataclass(slots=True)
class McpSession:
    """One packaged ``cadrumo-mcp`` process and its MCP client session."""

    client: ClientSession
    calls: list[str] = field(default_factory=list)

    async def call(self, tool: str, arguments: Mapping[str, object]) -> tuple[bool, dict[str, Any]]:
        """Call one tool and return whether it was an error and its structured content."""
        self.calls.append(tool)
        result = await asyncio.wait_for(self.client.call_tool(tool, dict(arguments)), timeout=_CALL_SECONDS)
        content = result.structured_content if isinstance(result.structured_content, dict) else {}
        return bool(result.is_error), content


@asynccontextmanager
async def mcp_session(
    programs: Programs, environment: Mapping[str, str], directory: Path, *arguments: str
) -> AsyncIterator[McpSession]:
    """Run the packaged MCP server over stdio for the life of the block."""
    server = StdioServerParameters(
        command=str(programs.mcp), args=list(arguments), env=dict(environment), cwd=str(directory)
    )
    with open(os.devnull, "w", encoding="utf-8") as errors:
        async with (
            stdio_client(server, errlog=errors) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream, read_timeout_seconds=None) as client,
        ):
            await client.initialize()
            yield McpSession(client)


_PROFILE_PROBE: tuple[str, dict[str, object]] = ("describe", {"definition_id": "user-profile.view"})
"""A call answered only under a session, so it asks to be admitted when none is held."""


def _refused_code(content: Mapping[str, Any]) -> str | None:
    code = content.get("code")
    return code if isinstance(code, str) else None


def _descends_from_harness(process_id: int) -> bool:
    """Whether the kernel-named asking process descends from this harness, which launched the MCP server."""
    try:
        return any(parent.pid == os.getpid() for parent in psutil.Process(process_id).parents())
    except psutil.Error:
        return False


async def _ask_and_decide(
    holder: Holder, session: McpSession, *, approve: bool, receipt: Receipt, step: str
) -> tuple[bool, dict[str, Any]]:
    """Make one profile call that asks to be attended, verify the asking process, decide it, and return the call."""
    call = asyncio.ensure_future(session.call(*_PROFILE_PROBE))
    ask = await asyncio.to_thread(holder.event, "attendance_request")
    process_id = ask.get("process_id")
    if not isinstance(process_id, int):
        raise AcceptanceError(f"the ask names no process: {ask}")
    require(_descends_from_harness(process_id), f"the asking process {process_id} was not launched by this harness")
    require(process_id != holder.process.pid, "the ask came from the holder itself")
    decided = await asyncio.to_thread(holder.decide, str(ask["attendance_id"]), approve=approve)
    require(decided.get("approved") is approve, f"the holder applied another answer: {decided}")
    is_error, content = await call
    receipt.record(step, process_id_verified=True, approved=approve, call_error=is_error, code=_refused_code(content))
    return is_error, content


async def _authenticated_read(session: McpSession, profile: Profile) -> dict[str, Any]:
    """Run ``user-profile.view`` for the profile's status page and return its settled result."""
    is_error, submitted = await session.call(
        "execute",
        {
            "definition_id": "user-profile.view",
            "payload": {"profile_id": str(profile.profile_id), "page_kind": "status"},
            "start": True,
        },
    )
    require(not is_error, f"execute refused: {submitted}")
    operation_id = (submitted.get("receipt") or {}).get("operation_id")
    require(isinstance(operation_id, str), f"execute named no operation: {submitted}")
    deadline = time.monotonic() + _CALL_SECONDS
    while True:
        is_error, result = await session.call("result", {"result": {"operation_id": operation_id}})
        if not is_error and result.get("outcome") != "pending":
            return result
        require(time.monotonic() < deadline, f"the read did not settle: {result}")
        await asyncio.sleep(0.5)


async def _require_refused(session: McpSession, receipt: Receipt, step: str) -> str | None:
    is_error, content = await session.call(*_PROFILE_PROBE)
    require(is_error, f"{step}: the profile call was answered: {content}")
    code = _refused_code(content)
    receipt.record(step, refused=True, code=code)
    return code


async def _admit(holder: Holder, session: McpSession, profile: Profile, receipt: Receipt, step: str) -> dict[str, Any]:
    is_error, content = await _ask_and_decide(holder, session, approve=True, receipt=receipt, step=step)
    require(not is_error, f"{step}: the approved connection was refused: {content}")
    _status_error, status = await session.call("status", {})
    require(status.get("session") == "attended", f"{step}: not attended: {status}")
    admitted = status.get("status") or {}
    require(admitted.get("profile_id") == str(profile.profile_id), f"{step}: another profile: {status}")
    read = await _authenticated_read(session, profile)
    text = json.dumps(read)
    require(profile.name in text, f"{step}: the read did not return the profile's own label: {text[:400]}")
    receipt.record(f"{step}_read", session=status.get("session"), label_returned=True)
    return read


def _create(programs: Programs, environment: Mapping[str, str], name: str, log: Path) -> Profile:
    """Create a profile, then learn its id from the ``held`` event of a brief hold.

    Command output hides profile identifiers, so the id comes from the one
    public interface that names it to the person holding the sign-in.
    """
    password = secrets.token_urlsafe(32)
    code, envelope = run_cli(
        programs,
        environment,
        "config",
        "profile",
        "create",
        name,
        "--quiet",
        "--secrets-stdin",
        secret={"passphrase": password, "passphrase_confirmation": password},
    )
    require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile create: {code} {envelope}")
    return Profile(name, password, UUID(int=0))


def _identify(programs: Programs, environment: Mapping[str, str], profile: Profile, log: Path) -> Profile:
    holder = Holder(programs, environment, profile, log)
    try:
        held = holder.event("held")
        holder.close_input()
        reason, exit_code = holder.finish()
        require(reason == "input_closed" and exit_code == 0, f"brief hold of {profile.name}: {reason} {exit_code}")
    finally:
        holder.stop()
    return Profile(profile.name, profile.password, UUID(str(held["profile_id"])))


def _identity(package: Path | None) -> dict[str, object]:
    if package is None:
        return {"package": None}
    manifest = package / "data" / "package-manifest.json"
    build = package / "data" / "build.json"
    return {
        "package": str(package),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None,
        "build": json.loads(build.read_text(encoding="utf-8")) if build.is_file() else None,
    }


def _started_processes() -> list[str]:
    survivors = []
    for child in psutil.Process(os.getpid()).children(recursive=True):
        with suppress(psutil.Error):
            if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                survivors.append(f"{child.pid}:{child.name()}")
    return survivors


async def run(programs: Programs, package: Path | None, scratch: Path, *, expiry: bool) -> Receipt:
    """Execute the whole lifecycle on a fresh root below ``scratch``."""
    receipt = Receipt()
    receipt.record("artifact", **_identity(package))
    root, secret_store = scratch / "storage", scratch / "secrets"
    secret_store.mkdir(parents=True)
    environment = consumer_environment(root, secret_store)
    if package is None:
        # A package carries its own published authority; a development environment names the checkout's.
        environment["CADRUMO_AUTHORITY_ROOT"] = os.environ.get(
            "CADRUMO_AUTHORITY_ROOT", str(_REPOSITORY_ROOT / ".authority")
        )
    default_root = host_installed_default_root(os.environ)
    before = file_facts(default_root)
    log = scratch / "processes.log"

    help_run = subprocess.run(  # noqa: S603 -- exact packaged executable; no shell.
        [str(programs.aeat), "--language", "en", "config", "sign-in-hold", "--help"],
        env=dict(environment),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    require(help_run.returncode == 0 and "sign-in-hold" in help_run.stdout, f"no sign-in-hold: {help_run.stderr}")
    receipt.record("command_registered", command="config sign-in-hold")

    other = _create(programs, environment, _OTHER_PROFILE, log)
    profile = _create(programs, environment, _PROFILE, log)
    receipt.record("profiles_created", profiles=2)

    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        ready = runtime.ready()
        receipt.record("runtime_ready", product_version=ready.get("product_version"))
        other = _identify(programs, environment, other, log)
        profile = _identify(programs, environment, profile, log)
        receipt.record("profiles_identified_by_held_events", profiles=2)

        async with mcp_session(programs, environment, scratch) as agent:
            code = await _require_refused(agent, receipt, "refused_before_any_sign_in")
            require(code == "authentication_required", f"before sign-in: {code}")

            holder = Holder(programs, environment, profile, log)
            try:
                held = holder.event("held")
                receipt.record("held", session_expires_at=held.get("session_expires_at"))

                is_error, content = await _ask_and_decide(
                    holder, agent, approve=False, receipt=receipt, step="declined"
                )
                require(is_error and _refused_code(content) == "authentication_required", f"declined: {content}")

                async with mcp_session(programs, environment, scratch, "--profile-id", str(other.profile_id)) as wrong:
                    code = await _require_refused(wrong, receipt, "wrong_profile_refused")
                    require(code == "profile_mismatch", f"wrong profile: {code}")

                await _admit(holder, agent, profile, receipt, "approved")
                holder.sign_out()
                holder.event("signed_out")
                reason, exit_code = holder.finish()
                require(reason == "signed_out" and exit_code == 0, f"holder sign-out: {reason} {exit_code}")
                await _require_refused(agent, receipt, "refused_after_holder_sign_out")
            finally:
                holder.stop()

            holder = Holder(programs, environment, profile, log)
            try:
                holder.event("held")
                await _admit(holder, agent, profile, receipt, "approved_again")
                holder.close_input()
                reason, exit_code = holder.finish()
                require(reason == "input_closed" and exit_code == 0, f"holder input closed: {reason} {exit_code}")
                await _require_refused(agent, receipt, "refused_after_holder_input_closed")
            finally:
                holder.stop()

            holder = Holder(programs, environment, profile, log)
            try:
                holder.event("held")
                await _admit(holder, agent, profile, receipt, "approved_before_logout")
                code_, envelope = run_cli(
                    programs,
                    environment,
                    "config",
                    "logout",
                    "--secrets-stdin",
                    secret={"passphrase": profile.password},
                )
                require(code_ == 0, f"password-proven logout: {code_} {envelope}")
                receipt.record("logout_password_proven", exit_code=code_)
                reason, _exit = holder.finish()
                require(reason == "session_ended", f"holder after logout: {reason}")
                await _require_refused(agent, receipt, "refused_after_logout")
            finally:
                holder.stop()

            holder = Holder(programs, environment, profile, log)
            try:
                holder.event("held")
                await _admit(holder, agent, profile, receipt, "approved_before_lock")
                code_, envelope = run_cli(
                    programs,
                    environment,
                    "--profile-secrets-stdin",
                    "config",
                    "profile",
                    "lock",
                    "--all",
                    secret={"profile_passphrase": profile.password},
                )
                require(code_ == 0, f"profile lock: {code_} {envelope}")
                receipt.record("profile_locked", exit_code=code_)
                reason, _exit = holder.finish()
                require(reason == "session_ended", f"holder after lock: {reason}")
                await _require_refused(agent, receipt, "refused_after_lock")
            finally:
                holder.stop()
            code_, envelope = run_cli(
                programs,
                environment,
                "config",
                "profile",
                "resume",
                "--secrets-stdin",
                secret={"passphrase": profile.password},
            )
            require(code_ == 0, f"profile resume: {code_} {envelope}")
            receipt.record("profile_resumed", exit_code=code_)

            if expiry:
                holder = Holder(programs, environment, profile, log)
                try:
                    held = holder.event("held")
                    await _admit(holder, agent, profile, receipt, "approved_before_expiry")
                    deadline = datetime.fromisoformat(str(held["session_expires_at"])).timestamp()
                    wait = max(0.0, deadline - time.time()) + _EXPIRY_MARGIN_SECONDS
                    reason, _exit = holder.finish(seconds=wait + _EVENT_SECONDS)
                    require(reason == "session_ended", f"holder after expiry: {reason}")
                    await _require_refused(agent, receipt, "refused_after_expiry")
                finally:
                    holder.stop()
            else:
                receipt.unproven.append("expiry: skipped by --skip-expiry")

            holder = Holder(programs, environment, profile, log)
            try:
                holder.event("held")
                await _admit(holder, agent, profile, receipt, "approved_before_runtime_stop")
                stopped = runtime.stop()
                require(stopped == 64, f"runtime exit: {stopped}")
                receipt.record("runtime_stopped", exit_code=stopped)
                reason, _exit = holder.finish()
                require(reason == "session_ended", f"holder after runtime stop: {reason}")
                await _require_refused(agent, receipt, "refused_after_runtime_stop")
            finally:
                holder.stop()

    # Every operation that pauses for a review either reaches a remote service (Google), hands a row to a
    # language model (ledger classify and split reviews), or reviews a censal document no parser accepts.
    receipt.unproven.append(
        "reviewed operation: no review-gated operation runs here without a remote service, a model or a document"
    )
    receipts = sorted(str(path.relative_to(root)) for path in root.rglob("session.v2.json"))
    require(not receipts, f"a sign-in was stored: {receipts}")
    receipt.record("no_stored_sign_in", receipts=0)
    after = file_facts(default_root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    require(not changed, f"the installed default root changed: {changed[:20]}")
    receipt.record("default_root_unchanged", entries=len(after))
    survivors = _started_processes()
    require(not survivors, f"processes this run started survive it: {survivors}")
    receipt.record("no_surviving_processes")
    return receipt


def _programs(options: argparse.Namespace) -> tuple[Programs, Path | None]:
    if options.package is not None:
        package = Path(options.package).resolve(strict=True)
        return Programs.of(package), package
    suffix = ".exe" if sys.platform == "win32" else ""
    directory = Path(options.programs).resolve(strict=True)
    names = ("aeat", "cadrumo-runtime", "cadrumo-mcp")
    return Programs(*((directory / f"{name}{suffix}").resolve(strict=True) for name in names)), None


def _acceptance_failure(error: BaseException) -> str | None:
    """Find the contradicted step inside the task groups the MCP client wraps it in."""
    if isinstance(error, AcceptanceError):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            reason = _acceptance_failure(inner)
            if reason is not None:
                return reason
    return None


def main(arguments: list[str] | None = None) -> int:
    """Run the lifecycle; exit 0 when every step held, 1 on a contradicted step, 3 when a step was left out."""
    parser = argparse.ArgumentParser(prog="live-sign-in", description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--package", type=Path, help="A built package directory, such as stage/<config>/app.")
    source.add_argument("--programs", type=Path, help="A directory of entry points; not package acceptance.")
    parser.add_argument("--skip-expiry", action="store_true", help="Leave out the wait for the sign-in deadline.")
    parser.add_argument("--keep", action="store_true", help="Keep the disposable root for inspection.")
    options = parser.parse_args(arguments)
    programs, package = _programs(options)
    base = _REPOSITORY_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="live-sign-in-", dir=base))
    try:
        receipt = asyncio.run(run(programs, package, scratch, expiry=not options.skip_expiry))
    except (AcceptanceError, BaseExceptionGroup) as failure:
        reason = _acceptance_failure(failure)
        if reason is None:
            raise
        print(json.dumps({"step": "failed", "reason": reason, "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    if package is None:
        receipt.unproven.append("package: ran against a programs directory, not a built package")
    if receipt.unproven:
        print(json.dumps({"step": "incomplete", "unproven": receipt.unproven}), flush=True)
        return 3
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
