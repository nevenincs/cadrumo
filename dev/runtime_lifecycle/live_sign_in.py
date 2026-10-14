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
- an approved connection is admitted as ``attended``, searches its operations
  and reads the profile's own known data through a registered operation;
- a reviewed operation pauses for the person's decision: a ledger row is
  classified by a local model on this machine, the review is read, inspected
  and applied, and the classification is read back through the command line;
- signing out from the holder, closing the holder's input, a password-proven
  ``config logout`` from another process, a profile-wide lock, the sign-in's
  own deadline, and stopping the runtime each end that access;
- no stored sign-in is written, the person's own Cadrumo data is unchanged,
  and no process this run started survives it.

Run it with ``just verify-live-sign-in PACKAGE``. ``--programs`` points at a
directory of entry points instead, such as a development environment's
scripts, for a quick run that is not package acceptance. ``--skip-expiry``
leaves out the step that waits for the sign-in's own deadline. The reviewed
step runs a harness-owned ``ollama serve`` on the loopback port, reading an
existing model store without pruning it, and stops it afterwards; with no local
model the step is reported unproven. ``--skip-review`` leaves it out.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
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
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import psutil
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.core.storage_environment import host_installed_default_root
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path

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
_OLLAMA_URL = "http://127.0.0.1:11434"
_LOCAL_TEXT_MODEL = "qwen3:1.7b"
_REVIEW_SECONDS = 600
_TAXPAYER_FACTS = (
    *("--entity-type", "natural_person", "--tax-id", "12345678Z", "--name", "Daniel", "--surnames", "Persona"),
    *("--activity", "consultoria", "--activity-start-date", "2026-01-01"),
    *("--irpf-income-categories", "actividad_economica", "--irpf-estimation-regime", "directa_normal"),
    *("--iva-regime", "GENERAL", "--tax-residence-jurisdiction-scope", "common_regime"),
    *("--iva-m303-regime-composition", "general", "--no-iva-redeme-enrolled"),
    *("--no-iva-cash-accounting-regime-enrolled", "--no-iva-voluntary-sii-enrolled"),
    "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
    *("--fiscal-residency", "resident_irpf", "--tax-residence-ccaa", "madrid"),
)
"""Synthetic taxpayer facts, those of the live-agent lane's published worked example."""


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
) -> AsyncGenerator[McpSession]:
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


async def ask_and_decide(
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
    is_error, content = await ask_and_decide(holder, session, approve=True, receipt=receipt, step=step)
    require(not is_error, f"{step}: the approved connection was refused: {content}")
    _status_error, status = await session.call("status", {})
    require(status.get("session") == "attended", f"{step}: not attended: {status}")
    admitted = status.get("status") or {}
    require(admitted.get("profile_id") == str(profile.profile_id), f"{step}: another profile: {status}")
    is_error, found = await session.call("search", {})
    require(not is_error and found.get("outcome") == "found", f"{step}: unfiltered search failed: {found}")
    read = await _authenticated_read(session, profile)
    text = json.dumps(read)
    require(profile.name in text, f"{step}: the read did not return the profile's own label: {text[:400]}")
    receipt.record(f"{step}_read", session=status.get("session"), label_returned=True, search_found=True)
    return read


def create_profile(programs: Programs, environment: Mapping[str, str], name: str, log: Path) -> Profile:
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


def identify_profile(programs: Programs, environment: Mapping[str, str], profile: Profile, log: Path) -> Profile:
    """Learn a profile's id from the ``held`` event of a brief hold, then let the hold go."""
    holder = Holder(programs, environment, profile, log)
    try:
        held = holder.event("held")
        holder.close_input()
        reason, exit_code = holder.finish()
        require(reason == "input_closed" and exit_code == 0, f"brief hold of {profile.name}: {reason} {exit_code}")
    finally:
        holder.stop()
    return Profile(profile.name, profile.password, UUID(str(held["profile_id"])))


def model_store(chosen: Path | None) -> Path:
    """Return the Ollama model store to read: the chosen one, else Cadrumo's own.

    Cadrumo's Ollama processes keep their weights in the storage root's
    model member, so that member is the store this proof reads by default.
    """
    return chosen if chosen is not None else storage_path(StorageCategory.OLLAMA_MODELS)


@contextlib.contextmanager
def local_model(scratch: Path, models: Path) -> Generator[bool]:
    """Serve the local text model on the loopback port for the block; say whether it is available.

    A server this harness did not start is never used or stopped. Ollama's
    pruning of blobs it does not recognise is switched off, so an existing
    model store is only read.
    """
    try:
        httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=1)
    except httpx.HTTPError:
        pass
    else:
        raise AcceptanceError("a model server already listens on the loopback port; this run uses only its own")
    found = shutil.which("ollama") or str(
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    )
    if not Path(found).is_file() or not models.is_dir():
        yield False
        return
    environment = {**os.environ, "OLLAMA_MODELS": str(models), "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NOPRUNE": "1"}
    with (scratch / "ollama.log").open("wb") as output:
        server = subprocess.Popen(  # noqa: S603 -- the installed local model server; no shell.
            [found, "serve"], env=environment, stdout=output, stderr=subprocess.STDOUT
        )
        try:
            deadline = time.monotonic() + 60
            tags = None
            while tags is None and time.monotonic() < deadline:
                with contextlib.suppress(httpx.HTTPError):
                    tags = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=1).json()
                time.sleep(0.5)
            names = {item.get("name") for item in (tags or {}).get("models", [])}
            yield _LOCAL_TEXT_MODEL in names
        finally:
            # The server starts a model runner per loaded model; stopping only the server leaves it running.
            with suppress(psutil.Error):
                tree = [psutil.Process(server.pid), *psutil.Process(server.pid).children(recursive=True)]
                for process in tree:
                    with suppress(psutil.Error):
                        process.terminate()
                _gone, alive = psutil.wait_procs(tree, timeout=30)
                for process in alive:
                    with suppress(psutil.Error):
                        process.kill()
                psutil.wait_procs(alive, timeout=30)
            server.wait(timeout=30)


def state_taxpayer(programs: Programs, environment: Mapping[str, str], profile: Profile) -> None:
    """State the synthetic taxpayer facts and complete the setup, as the person does at the command line."""
    for arguments in (
        ("config", "profile", "edit", "--quiet", *_TAXPAYER_FACTS),
        ("config", "profile", "complete-setup"),
    ):
        code, envelope = run_cli(
            programs,
            environment,
            "--profile-secrets-stdin",
            *arguments,
            secret={"profile_passphrase": profile.password},
        )
        require(code == 0, f"{' '.join(arguments[:3])}: {code} {envelope}")


async def observe(session: McpSession, operation_id: str) -> dict[str, Any]:
    """Return the operation's current projection as the agent observes it."""
    is_error, observed = await session.call(
        "observe", {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}}
    )
    require(not is_error, f"observe refused: {observed}")
    return observed["reply"]["observation"]["projection"]


async def execute(session: McpSession, definition_id: str, payload: Mapping[str, object]) -> str:
    """Submit and start a registered operation through MCP; return the operation id its receipt names."""
    is_error, submitted = await session.call(
        "execute", {"definition_id": definition_id, "payload": dict(payload), "start": True}
    )
    require(not is_error, f"{definition_id} refused: {submitted}")
    operation_id = (submitted.get("receipt") or {}).get("operation_id")
    require(isinstance(operation_id, str), f"{definition_id} named no operation: {submitted}")
    return str(operation_id)


async def settled(session: McpSession, operation_id: str) -> dict[str, Any]:
    """Wait until the operation's result is terminal and return it."""
    deadline = time.monotonic() + _CALL_SECONDS
    while True:
        is_error, result = await session.call("result", {"result": {"operation_id": operation_id}})
        document = result.get("document") or {}
        if not is_error and document.get("code") != "operation_not_terminal":
            return result
        require(time.monotonic() < deadline, f"the operation did not settle: {result}")
        await asyncio.sleep(1)


async def _reviewed_classification(
    session: McpSession, programs: Programs, environment: Mapping[str, str], profile: Profile, receipt: Receipt
) -> None:
    """Classify one ledger row through the local model, answer its review, and read the outcome independently."""
    description = "Papeleria y material de oficina"
    added = await settled(
        session,
        await execute(
            session,
            "ledger.add",
            {
                "profile_id": str(profile.profile_id),
                "booked_date": "2026-07-15",
                "amount": "121.00",
                "direction": "OUTGOING",
                "description": description,
                "counterparty": "Papeleria Central SL",
            },
        ),
    )
    row = ((added.get("document") or {}).get("projection") or {}).get("transaction") or {}
    transaction_id = row.get("transaction_id")
    if not isinstance(transaction_id, str):
        raise AcceptanceError(f"ledger.add created no row: {added}")
    review_id = await execute(
        session,
        "ledger.classify.review",
        {
            "profile_id": str(profile.profile_id),
            "transaction_id": transaction_id,
            "mode": "classification",
            "origin": "classify_llm_apply",
        },
    )
    deadline = time.monotonic() + _REVIEW_SECONDS
    while True:
        projection = await observe(session, review_id)
        pending = projection.get("pending_interaction") or {}
        if pending.get("disposition") == "review_available":
            break
        require(projection.get("terminal_condition") is None, f"the review ended without a decision: {projection}")
        require(time.monotonic() < deadline, "the local model proposed nothing in time")
        await asyncio.sleep(2)
    require(projection.get("effect") == "none", f"something was written before the decision: {projection}")
    is_error, proposal = await session.call("review", {"review": {"reference": pending["review_reference"]}})
    require(not is_error, f"review read refused: {proposal}")
    answer = {
        "operation_id": pending["operation_id"],
        "interaction_id": pending["interaction_id"],
        "revision": pending["revision"],
    }
    is_error, inspected = await session.call("respond", {"action": "inspect", **answer})
    document = (inspected.get("reply") or {}).get("document") or {}
    require(not is_error and "apply" in document.get("permitted_intents", ()), f"inspect: {inspected}")
    is_error, applied = await session.call("respond", {"action": "apply", **answer})
    require(not is_error, f"apply refused: {applied}")
    outcome = await settled(session, review_id)
    projection = (outcome.get("document") or {}).get("projection") or {}
    classified = projection.get("classification") or {}
    stored = classified.get("transaction") or {}
    require(classified.get("outcome") == "classified", f"not classified: {outcome}")
    require(classified.get("review_status") == "reviewed", f"not reviewed: {outcome}")
    require(str(stored.get("classified_by", "")).startswith("llm:local-text:"), f"not the local model: {stored}")
    code, listing = run_cli(
        programs,
        environment,
        "--profile-secrets-stdin",
        "app",
        "ledger",
        "list",
        secret={"profile_passphrase": profile.password},
    )
    text = json.dumps(listing)
    require(code == 0 and transaction_id in text, f"the command line does not list the row: {code} {text[:400]}")
    require(stored.get("business_classification", "") in text, "the command line reads another classification")
    receipt.record(
        "reviewed_operation",
        model=stored.get("classified_by"),
        classification=stored.get("business_classification"),
        review_status=classified.get("review_status"),
        written_before_decision=False,
        read_back_by_command_line=True,
    )


def package_identity(package: Path | None) -> dict[str, object]:
    """Name the package under test by its manifest digest and build record."""
    if package is None:
        return {"package": None}
    manifest = package / "data" / "package-manifest.json"
    build = package / "data" / "build.json"
    return {
        "package": str(package),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else None,
        "build": json.loads(build.read_text(encoding="utf-8")) if build.is_file() else None,
    }


def started_processes() -> list[str]:
    """List this driver's descendant processes that are still running."""
    survivors = []
    for child in psutil.Process(os.getpid()).children(recursive=True):
        with suppress(psutil.Error):
            if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                survivors.append(f"{child.pid}:{child.name()}")
    return survivors


async def run(
    programs: Programs, package: Path | None, scratch: Path, *, expiry: bool, review: bool, models: Path
) -> Receipt:
    """Execute the whole lifecycle on a fresh root below ``scratch``."""
    receipt = Receipt()
    receipt.record("artifact", **package_identity(package))
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

    other = create_profile(programs, environment, _OTHER_PROFILE, log)
    profile = create_profile(programs, environment, _PROFILE, log)
    receipt.record("profiles_created", profiles=2)

    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        ready = runtime.ready()
        receipt.record("runtime_ready", product_version=ready.get("product_version"))
        other = identify_profile(programs, environment, other, log)
        profile = identify_profile(programs, environment, profile, log)
        receipt.record("profiles_identified_by_held_events", profiles=2)
        if review:
            state_taxpayer(programs, environment, profile)
            receipt.record("taxpayer_stated")

        async with mcp_session(programs, environment, scratch) as agent:
            code = await _require_refused(agent, receipt, "refused_before_any_sign_in")
            require(code == "authentication_required", f"before sign-in: {code}")

            holder = Holder(programs, environment, profile, log)
            try:
                held = holder.event("held")
                receipt.record("held", session_expires_at=held.get("session_expires_at"))

                is_error, content = await ask_and_decide(holder, agent, approve=False, receipt=receipt, step="declined")
                require(is_error and _refused_code(content) == "authentication_required", f"declined: {content}")

                async with mcp_session(programs, environment, scratch, "--profile-id", str(other.profile_id)) as wrong:
                    code = await _require_refused(wrong, receipt, "wrong_profile_refused")
                    require(code == "profile_mismatch", f"wrong profile: {code}")

                await _admit(holder, agent, profile, receipt, "approved")
                if review:
                    with local_model(scratch, models) as available:
                        if available:
                            await _reviewed_classification(agent, programs, environment, profile, receipt)
                        else:
                            receipt.unproven.append(f"reviewed operation: no local {_LOCAL_TEXT_MODEL} model to serve")
                else:
                    receipt.unproven.append("reviewed operation: skipped by --skip-review")
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

    receipts = sorted(str(path.relative_to(root)) for path in root.rglob("session.v2.json"))
    require(not receipts, f"a sign-in was stored: {receipts}")
    receipt.record("no_stored_sign_in", receipts=0)
    after = file_facts(default_root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    require(not changed, f"the installed default root changed: {changed[:20]}")
    receipt.record("default_root_unchanged", entries=len(after))
    survivors = started_processes()
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


def acceptance_failure(error: BaseException) -> str | None:
    """Find the contradicted step inside the task groups the MCP client wraps it in."""
    if isinstance(error, AcceptanceError):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            reason = acceptance_failure(inner)
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
    parser.add_argument("--skip-review", action="store_true", help="Leave out the reviewed ledger operation.")
    parser.add_argument(
        "--ollama-models",
        type=Path,
        default=None,
        help="An existing Ollama model store to read (default: Cadrumo's own); nothing is pulled or pruned.",
    )
    options = parser.parse_args(arguments)
    programs, package = _programs(options)
    base = _REPOSITORY_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="live-sign-in-", dir=base))
    try:
        receipt = asyncio.run(
            run(
                programs,
                package,
                scratch,
                expiry=not options.skip_expiry,
                review=not options.skip_review,
                models=model_store(options.ollama_models),
            )
        )
    except (AcceptanceError, BaseExceptionGroup) as failure:
        reason = acceptance_failure(failure)
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
