"""Be the person behind a live agent run on the built package, and judge its outcome independently.

The external agent's runner starts the manifest-verified bundled native gateway, with
the package's ``cadrumo-mcp`` as the tool relay, and drives the turns.
This driver never starts the agent and never
holds its bearer. On a fresh, marked storage root it:

- starts the package's ``cadrumo-runtime --configured-root`` and creates a
  disposable profile with synthetic taxpayer facts through the package's
  ``aeat``, the password on its standard input only;
- signs that profile in and holds the sign-in;
- writes the hand-off for the runner into a private exchange directory and
  waits for it;
- approves a Cadrumo attendance ask only from the package's relay running under
  the gateway the runner announced, and denies every other ask;
- answers each permission request the runner files by approving it once, and
  fails the run when a request offers no single allow-once option; it judges the
  run by its outcome, not by which tools were asked for;
- reads the runner's receipt and checks it against what it saw itself: the
  reply names the taxpayer, ``aeat`` lists the scenario's ledger row exactly
  once, and the answers the gateway stored are the answers given here;
- stops the runtime and requires that nothing it started survives.

The exchange directory holds JSON files written whole, each by one side:

- ``handoff.json`` (this driver): the package, the storage root, the profile,
  the relay and the scenario;
- ``gateway.json`` (runner): the gateway's process id, its URL, its home and its
  workspace;
- ``requests/<n>.json`` (runner): a pending permission, as the gateway's run
  status serves it, with its run id;
- ``answers/<n>.json`` (this driver): ``{"option_id": ...}`` naming an offered
  ``allow_once`` option, or ``{"decision": "reject"}``;
- ``runner-receipt.json`` or ``runner-failed.json`` (runner): how the agent side
  ended.

Run it with ``--package DIR``, then start the external agent's
package runner on the exchange directory it prints. Exit 0 means every step
held, 1 names the step that did not.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import psutil

from cadrumo_runtime.application.development_root import mark_development_root
from dev._paths import REPO_ROOT

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    Receipt,
    caller_owned_runtime,
    consumer_environment,
    require,
    run_cli,
)
from .proof_support import (
    ProcessIdentity,
    Profile,
    acceptance_failure,
    create_profile,
    identify_profile,
    package_identity,
    started_processes,
    state_taxpayer,
    verified_relay,
)
from .session_holder import AsyncRuntimeSessionHolder

_PROFILE: Final = "agent-live-acceptance"
_PROTOCOL: Final = 1
_SCENARIO: Final[dict[str, Any]] = {
    "taxpayer": "Daniel Persona",
    "ledger": {"description": "agent live acceptance", "amount": "12.34", "currency": "EUR", "date": "2026-01-15"},
}
_GATEWAY_SECONDS: Final = 600.0
_RUN_SECONDS: Final = 1800.0
_POLL_SECONDS: Final = 0.5


def write_whole(path: Path, document: Mapping[str, Any]) -> None:
    """Write ``document`` so a reader never sees a partial file: a sibling first, then a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(partial, path)


def read_document(path: Path) -> dict[str, Any] | None:
    """Return a whole JSON object the other side wrote, or ``None`` while it is absent."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    require(isinstance(document, dict), f"{path.name} is not a JSON object")
    require(document.get("version", _PROTOCOL) == _PROTOCOL, f"{path.name} speaks protocol {document.get('version')}")
    return document


def answer_for(request: Mapping[str, Any]) -> dict[str, str]:
    """Return the person's answer to one pending permission.

    The answer names the single ``allow_once`` option the request itself
    offered. When the request offers no single ``allow_once`` option the answer
    is a rejection, and the caller fails the run.
    """
    options = request.get("options")
    once = [
        option["option_id"]
        for option in options or ()
        if isinstance(option, Mapping)
        and option.get("kind") == "allow_once"
        and isinstance(option.get("option_id"), str)
    ]
    if len(once) == 1:
        return {"option_id": once[0]}
    return {"decision": "reject"}


def _as_answer(decision: object) -> dict[str, Any] | None:
    """Read the gateway's own recorded decision as the answer it records, or ``None`` when it is not one."""
    if not isinstance(decision, Mapping):
        return None
    if decision.get("action") == "approved":
        return {"option_id": decision.get("option_id")}
    if decision.get("action") == "rejected":
        return {"decision": "reject"}
    return None


def stored_answers_disagree(given: Mapping[str, Mapping[str, str]], stored: list[Any]) -> list[str]:
    """Name every difference between the answers given here and the ones the gateway stored, by request id.

    Each entry carries both the answer the runner relayed and the gateway's own
    recorded decision; both must be the answer given here.
    """
    relayed: dict[str, Any] = {}
    recorded: dict[str, Any] = {}
    for entry in stored:
        request = entry.get("request") if isinstance(entry, Mapping) else None
        request_id = request.get("request_id") if isinstance(request, Mapping) else None
        if not isinstance(request_id, str):
            return [f"a stored permission names no request: {entry!r}"]
        relayed[request_id] = entry.get("answer")
        recorded[request_id] = _as_answer(entry.get("stored"))
    differences = [
        f"{request_id}: given {answer}, relayed {relayed.get(request_id)}, stored {recorded.get(request_id)}"
        for request_id, answer in given.items()
        if relayed.get(request_id) != answer or recorded.get(request_id) != answer
    ]
    differences.extend(f"{request_id}: stored but never given here" for request_id in recorded.keys() - given.keys())
    return differences


def is_announced_relay(process_id: int, relay: Path, gateway: ProcessIdentity | None) -> bool:
    """Check the selected gateway's retained kernel incarnation and relay lineage."""
    return verified_relay(process_id, relay, gateway)


@dataclass(slots=True)
class Exchange:
    """The private directory this driver and the runner exchange whole files through."""

    directory: Path
    given: dict[str, dict[str, str]] = field(default_factory=dict)
    answered: set[str] = field(default_factory=set)

    def gateway(self) -> dict[str, Any] | None:
        """Return the runner's gateway announcement, or ``None`` before it is written."""
        return read_document(self.directory / "gateway.json")

    def ended(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return the runner's receipt and its failure, each ``None`` until written."""
        return read_document(self.directory / "runner-receipt.json"), read_document(
            self.directory / "runner-failed.json"
        )

    def answer_pending(self) -> list[str]:
        """Answer each request the runner filed since the last call; return those with no single allow-once option."""
        rejected: list[str] = []
        requests = self.directory / "requests"
        for path in sorted(requests.glob("*.json")) if requests.is_dir() else ():
            if path.name in self.answered:
                continue
            request = read_document(path)
            if request is None:
                continue
            answer = answer_for(request)
            write_whole(self.directory / "answers" / path.name, answer)
            self.answered.add(path.name)
            self.given[str(request.get("request_id"))] = answer
            print(
                json.dumps(
                    {"step": "permission_answered", "tool_call": request.get("tool_call"), "answer": answer},
                    sort_keys=True,
                ),
                flush=True,
            )
            if answer == {"decision": "reject"}:
                rejected.append(f"{request.get('tool_call')!r}: {request.get('description')!r}")
        return rejected


@asynccontextmanager
async def _attending(
    holder: AsyncRuntimeSessionHolder, relay: Path, gateway: Mapping[str, ProcessIdentity | None]
) -> AsyncGenerator[list[int]]:
    """Approve, for the life of the block, each attendance ask from the announced gateway's relay."""
    stop = asyncio.Event()
    approved: list[int] = []
    failures: list[str] = []

    async def attend() -> None:
        while not stop.is_set():
            try:
                inventory = await holder.command("attendance_inventory")
                require(inventory.get("kind") == "attendance_inventory", "runtime returned no attendance inventory")
                candidates = inventory.get("candidates")
                if not isinstance(candidates, list):
                    raise AcceptanceError("runtime attendance inventory has no candidate list")
                if stop.is_set():
                    return
                for ask in candidates:
                    if stop.is_set():
                        return
                    require(isinstance(ask, dict), "runtime attendance candidate is not an object")
                    require(isinstance(ask.get("attendance_id"), str), "runtime candidate omitted its ask identity")
                    process_id = ask.get("process_id")
                    relay_ask = type(process_id) is int and is_announced_relay(
                        process_id, relay, gateway.get("identity")
                    )
                    decision = await holder.command(
                        "attendance_decision", attendance_id=str(ask["attendance_id"]), approve=relay_ask
                    )
                    require(
                        decision.get("kind") == "attendance_decided" and decision.get("approved") is relay_ask,
                        "runtime attendance decision differs from the person's answer",
                    )
                    if relay_ask:
                        approved.append(process_id)
            except (AcceptanceError, OSError, ValueError) as refusal:
                failures.append(str(refusal))
                return
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=_POLL_SECONDS)

    watcher = asyncio.create_task(attend(), name="agent-live-attendance")
    try:
        yield approved
    finally:
        stop.set()
        await watcher
    require(not failures, f"attendance: {failures}")


def _ledger_text(programs: Programs, environment: Mapping[str, str], profile: Profile) -> str:
    code, envelope = run_cli(
        programs,
        environment,
        "--profile-secrets-stdin",
        "app",
        "ledger",
        "list",
        secret={"profile_passphrase": profile.password},
    )
    require(code == 0, f"app ledger list: {code} {envelope}")
    return json.dumps(envelope.get("result"), ensure_ascii=False)


def _await_runner(
    exchange: Exchange, gateway: dict[str, ProcessIdentity | None], gateway_image: Path, gateway_digest: str
) -> dict[str, Any]:
    """Serve the runner until it ends: note its gateway, answer its requests, return its receipt."""
    started = time.monotonic()
    while True:
        receipt, failed = exchange.ended()
        if failed is not None:
            raise AcceptanceError(f"the runner failed at {failed.get('stage')}: {failed.get('reason')}")
        if gateway.get("identity") is None and (announced := exchange.gateway()) is not None:
            require(type(announced.get("pid")) is int, "gateway.json names no process")
            identity = ProcessIdentity.capture(announced["pid"])
            require(identity.image == gateway_image, "announced gateway differs from the selected executable")
            require(
                identity.birth >= (exchange.directory / "handoff.json").stat().st_mtime,
                "announced gateway predates this invocation's handoff",
            )
            require(
                hashlib.sha256(gateway_image.read_bytes()).hexdigest() == gateway_digest,
                "announced gateway image differs from the packaged manifest",
            )
            require(
                psutil.Process(identity.pid).username() == psutil.Process().username(),
                "announced gateway belongs to another OS user",
            )
            gateway["identity"] = identity
            print(json.dumps({"step": "gateway_announced", "gateway_url": announced.get("gateway_url")}), flush=True)
        rejected = exchange.answer_pending()
        require(not rejected, f"a permission request offered no single allow-once option: {rejected}")
        if receipt is not None:
            return receipt
        elapsed = time.monotonic() - started
        require(gateway.get("identity") is not None or elapsed < _GATEWAY_SECONDS, "the runner announced no gateway")
        require(elapsed < _RUN_SECONDS, "the runner never ended")
        time.sleep(_POLL_SECONDS)


def _judge(receipt: Mapping[str, Any], exchange: Exchange, root: Path, after: str) -> dict[str, Any]:
    """Check the runner's receipt against what this driver saw; return the facts worth keeping."""
    require(receipt.get("storage_root_passed") == str(root), f"the runner passed another root: {receipt}")
    replies = " ".join(str(run.get("reply", "")) for run in receipt.get("runs", ()) if isinstance(run, Mapping))
    require(_SCENARIO["taxpayer"].lower() in replies.lower(), "no reply names the profile's taxpayer")
    disagreements = stored_answers_disagree(exchange.given, list(receipt.get("permissions", ())))
    require(not disagreements, f"the gateway stored other answers than were given: {disagreements}")
    require(bool(exchange.given), "the agent asked no permission, so no relay call was approved")
    description = _SCENARIO["ledger"]["description"]
    require(after.count(description) == 1, f"the ledger holds the scenario row {after.count(description)} times")
    return {
        "runs": [run.get("run_id") for run in receipt.get("runs", ()) if isinstance(run, Mapping)],
        "proofs": receipt.get("proofs"),
        "permissions_given": len(exchange.given),
        "wheel_sha256": receipt.get("wheel_sha256"),
    }


async def run(package: Path, scratch: Path) -> Receipt:
    """Serve one runner on a fresh root below ``scratch``."""
    programs = Programs.of(package)
    gateway_image = package / "bin" / ("cadrumo-agent.exe" if sys.platform == "win32" else "cadrumo-agent")
    manifest = json.loads((package / "data" / "package-manifest.json").read_text(encoding="utf-8"))
    expected_digest = manifest.get("files", {}).get(gateway_image.relative_to(package).as_posix())
    require(isinstance(expected_digest, str), "package manifest does not declare its bundled agent image")
    require(not gateway_image.is_symlink() and gateway_image.is_file(), "bundled gateway image unavailable")
    require(
        hashlib.sha256(gateway_image.read_bytes()).hexdigest() == expected_digest,
        "bundled gateway image differs from the package manifest",
    )
    receipt = Receipt()
    receipt.record("artifact", **package_identity(package))
    root, secret_store, directory = scratch / "storage", scratch / "secrets", scratch / "exchange"
    secret_store.mkdir(parents=True)
    directory.mkdir()
    exchange = Exchange(directory)
    environment = consumer_environment(root, secret_store)
    profile = create_profile(programs, environment, _PROFILE)
    mark_development_root(root)
    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        receipt.record("runtime_ready", product_version=runtime.ready().get("product_version"))
        profile = identify_profile(programs, environment, profile)
        state_taxpayer(programs, environment, profile)
        before = _ledger_text(programs, environment, profile)
        require(_SCENARIO["ledger"]["description"] not in before, "the ledger already holds the scenario row")
        if profile.profile_id is None:
            raise AcceptanceError("created profile has no verified identity")
        holder = await AsyncRuntimeSessionHolder.start(
            programs.runtime,
            profile_id=profile.profile_id,
            environment=environment,
            password=bytearray(profile.password, "utf-8"),
            frontend="cli",
        )
        try:
            receipt.record("signed_in_and_held")
            gateway: dict[str, ProcessIdentity | None] = {"identity": None}
            async with _attending(holder, programs.mcp, gateway) as approved:
                write_whole(
                    directory / "handoff.json",
                    {
                        "version": _PROTOCOL,
                        "package": str(package),
                        "storage_root": str(root),
                        "profile": str(profile.profile_id),
                        "relay": str(programs.mcp),
                        "scenario": _SCENARIO,
                    },
                )
                receipt.record("exchange_ready", exchange=str(directory))
                runner = await asyncio.to_thread(
                    _await_runner, exchange, gateway, gateway_image.resolve(strict=True), expected_digest
                )
                after = _ledger_text(programs, environment, profile)
                receipt.record("agent_judged", attended_relays=len(approved), **_judge(runner, exchange, root, after))
            closed = await holder.command("close")
            require(closed.get("kind") == "session_closed", "runtime did not acknowledge held-session closure")
        finally:
            await holder.close()
        stopped = runtime.stop()
        require(stopped == 64, f"runtime exit: {stopped}")
        receipt.record("runtime_stopped", exit_code=stopped)
    survivors = started_processes()
    require(not survivors, f"processes this run started survive it: {survivors}")
    receipt.record("no_surviving_processes")
    return receipt


def main(arguments: list[str] | None = None) -> int:
    """Run the person side; exit 0 when every step held and 1 on a contradicted step."""
    parser = argparse.ArgumentParser(prog="agent-live", description=__doc__.splitlines()[0])
    parser.add_argument("--package", type=Path, required=True, help="A built package directory (stage/<Config>/app).")
    parser.add_argument("--keep", action="store_true", help="Keep the disposable root and exchange for inspection.")
    parser.add_argument(
        "--scratch-parent",
        type=Path,
        help="Parent for disposable data; choose a directory outside repositories for CLI provider proofs.",
    )
    options = parser.parse_args(arguments)
    package = Path(options.package).resolve(strict=True)
    # dev._paths deliberately redirects stdlib temp into the checkout. CLI
    # provider proofs need an explicit external root to avoid repository
    # instruction discovery in their isolated tool runtime.
    base = options.scratch_parent or REPO_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="agent-live-", dir=base))
    try:
        asyncio.run(run(package, scratch))
    except (AcceptanceError, BaseExceptionGroup) as failure:
        reason = acceptance_failure(failure)
        if reason is None:
            raise
        print(json.dumps({"step": "failed", "reason": reason, "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
