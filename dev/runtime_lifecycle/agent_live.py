"""Prove the live agent reads and changes a signed-in profile through Cadrumo's own tools, end to end.

Everything is a real process on a fresh storage root: the package's
``cadrumo-runtime --configured-root``, its ``aeat`` command line, a held
sign-in, the cadrumo-agent gateway from a cadrumo-agent checkout, the real
Anthropic API, and the package's own ``cadrumo-mcp`` as the agent's tool
relay. Nobody types anything: the person's steps go through the command line
with the password on its standard input, and the holder approves only an
attendance ask whose process this driver launched. The run proves, one
receipt line per step:

- a disposable profile with synthetic taxpayer facts, signed in and held;
- the agent answers a question about the profile with the taxpayer's name,
  which it can know only by calling Cadrumo's tools inside that profile;
- the agent adds one ledger row through Cadrumo's ``ledger.add`` operation,
  and the command line, an independent reader, lists exactly that row once;
- the gateway, its worker and the relay end with the run, the runtime stops,
  and nothing this run started survives.

It spends model credit. Run it with ``just verify-agent-live PACKAGE``. The
cadrumo-agent checkout comes from ``--agent-checkout`` or
``CADRUMO_AGENT_CHECKOUT``; its Anthropic key is read from that checkout's
``.env`` and given only to the gateway's own environment. Without a key the
run is reported unproven.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import psutil

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    Receipt,
    caller_owned_runtime,
    consumer_environment,
    require,
    run_cli,
)
from .live_sign_in import (
    Holder,
    Profile,
    acceptance_failure,
    create_profile,
    identify_profile,
    package_identity,
    started_processes,
    state_taxpayer,
)

_PROFILE = "agent-live-acceptance"
_TAXPAYER = "Daniel Persona"
_LEDGER_MARKER = "agent live acceptance"
_KEY_NAME = "CADRUMO_AGENT_CLAUDE_API_KEY"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_GATEWAY_START_SECONDS = 180
_RUN_START_SECONDS = 240
_TURN_SECONDS = 600


def _source_programs(directory: Path) -> Programs:
    """Locate the three entry points in a directory of console scripts."""
    suffix = ".exe" if os.name == "nt" else ""
    names = ("aeat", "cadrumo-runtime", "cadrumo-mcp")
    return Programs(*((directory / f"{name}{suffix}").resolve(strict=True) for name in names))


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _anthropic_key(checkout: Path) -> str | None:
    """Read the agent's Anthropic key from its checkout's operator file; never print it."""
    with suppress(OSError):
        for line in (checkout / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{_KEY_NAME}="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    return None


class _Gateway:
    """The cadrumo-agent gateway this run owns, reached over loopback with its own bearer."""

    def __init__(self, port: int, token: str, process: subprocess.Popen[bytes]) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self._token = token
        self.process = process

    def _request(self, method: str, path: str, body: Mapping[str, object] | None, timeout: float) -> Any:
        request = urllib.request.Request(  # noqa: S310 -- loopback gateway this run started.
            f"{self.base}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method=method,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise AcceptanceError(f"gateway {method} {path}: {error.code} {error.read()[:400]!r}") from None

    def wait_ready(self) -> None:
        deadline = time.monotonic() + _GATEWAY_START_SECONDS
        while time.monotonic() < deadline:
            require(self.process.poll() is None, f"the gateway exited during startup ({self.process.poll()})")
            with (
                suppress(OSError, urllib.error.URLError),
                urllib.request.urlopen(f"{self.base}/health", timeout=5) as response,  # noqa: S310
            ):
                if response.status == 200:
                    return
            time.sleep(1)
        raise AcceptanceError(f"the gateway did not answer /health in {_GATEWAY_START_SECONDS}s")

    def model(self, workspace: Path, requested: str | None) -> str:
        """Return the model to run: the requested one, or the catalog's own recommendation from the live API."""
        catalog = self._request(
            "GET", f"/v1/provider-catalog?workspace_root={urllib.parse.quote(str(workspace))}", None, 180
        )
        lane = next((lane for lane in catalog["providers"] if lane["provider_id"] == "anthropic"), None)
        if lane is None:
            raise AcceptanceError("the gateway offers no anthropic lane")
        require(lane["health"]["selectable"], f"the anthropic lane is not selectable: {lane['health']['reasons']}")
        models = lane["catalog"]["models"]
        require(bool(models), "the anthropic catalog lists no model")
        if requested is not None:
            require(any(entry["model"] == requested for entry in models), f"{requested} is not in the live catalog")
            return requested
        recommended = lane["catalog"].get("recommended_entry_id")
        chosen = next((entry for entry in models if entry["entry_id"] == recommended), models[0])
        return str(chosen["model"])

    def turn(
        self, workspace: Path, model: str, message: str, continues: str | None
    ) -> tuple[str, str, list[str], list[str]]:
        """Run one turn to its end, approving each tool call once as the person would.

        Returns the run id, the reply text, the Cadrumo tools it called and the
        approvals it was asked for. Only an ``allow_once`` option is chosen, so
        every later call must ask again.
        """
        run_id = str(uuid.uuid4())
        self._request(
            "POST",
            "/v1/runs",
            {
                "run_id": run_id,
                "message": message,
                "title": "agent live acceptance",
                **({"continues_run_id": continues} if continues is not None else {}),
                "agent": {"provider": "anthropic", "model": model, "workspace_root": str(workspace)},
            },
            _RUN_START_SECONDS,
        )
        stream = urllib.request.Request(  # noqa: S310 -- loopback gateway this run started.
            f"{self.base}/v1/runs/{run_id}/stream?last_event_id=-",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        reply: list[str] = []
        tools: list[str] = []
        approvals: list[str] = []
        status = None
        event = None
        with urllib.request.urlopen(stream, timeout=_TURN_SECONDS) as response:  # noqa: S310
            for raw in response:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("event:"):
                    event = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                data = json.loads(line[5:])
                if event == "message_chunk":
                    reply.append(str(data.get("content", "")))
                elif event == "tool_call_start" and data.get("title"):
                    tools.append(str(data["title"]))
                elif event == "permission_request":
                    option = next(
                        (choice for choice in data.get("options", []) if choice.get("kind") == "allow_once"), None
                    )
                    if option is None:
                        raise AcceptanceError(f"an approval offered no allow_once option: {data.get('options')}")
                    approvals.append(str(data.get("description") or data.get("tool_call")))
                    self._request(
                        "POST",
                        f"/v1/runs/{run_id}/permissions/{data['request_id']}/respond",
                        {"option_id": option["option_id"]},
                        60,
                    )
                elif event == "thread_terminal":
                    status = data.get("status")
                    break
        require(status == "completed", f"the turn ended {status}")
        return run_id, "".join(reply), tools, approvals


@contextmanager
def _gateway(
    checkout: Path, programs: Programs, environment: Mapping[str, str], scratch: Path, key: str
) -> Generator[_Gateway]:
    """Start the agent's gateway on this run's root, with the package's ``cadrumo-mcp`` as its tool relay."""
    port, token = _free_port(), secrets.token_hex(32)
    agent_environment = dict(environment)
    agent_environment.update(
        {
            "PATH": os.pathsep.join((str(programs.mcp.parent), environment.get("PATH", ""))),
            "CADRUMO_AGENT_PROJECT_ROOT": str(scratch / "agent"),
            "CADRUMO_AGENT_HOST": "127.0.0.1",
            "CADRUMO_AGENT_PORT": str(port),
            "CADRUMO_AGENT_WORKER_PORT": str(_free_port()),
            "CADRUMO_AGENT_ENVIRONMENT": "development",
            "CADRUMO_AGENT_GATEWAY_TOKEN": token,
            "CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER": "true",
            _KEY_NAME: key,
        }
    )
    (scratch / "agent").mkdir()
    with (scratch / "agent.log").open("wb") as log:
        process = subprocess.Popen(  # noqa: S603 -- the checkout's own console script; no shell.
            [str(checkout / ".venv" / "Scripts" / "cadrumo-agent.exe"), "serve"],
            cwd=scratch / "agent",
            env=agent_environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            gateway = _Gateway(port, token, process)
            gateway.wait_ready()
            yield gateway
        finally:
            tree = [process]
            with suppress(psutil.Error):
                tree = [psutil.Process(process.pid), *psutil.Process(process.pid).children(recursive=True)]
            for member in reversed(tree):
                with suppress(psutil.Error, ProcessLookupError):
                    member.terminate()
            psutil.wait_procs([p for p in tree if isinstance(p, psutil.Process)], timeout=20)
            for member in tree:
                with suppress(psutil.Error, ProcessLookupError):
                    member.kill()


@contextmanager
def _attending(holder: Holder) -> Generator[list[int]]:
    """Approve, for the life of the block, every attendance ask from a process this driver launched."""
    stop = threading.Event()
    approved: list[int] = []
    failures: list[str] = []

    def attend() -> None:
        while not stop.is_set():
            try:
                ask = holder.event("attendance_request", seconds=1)
            except AcceptanceError as refusal:
                if "sent no attendance_request" in str(refusal):
                    continue
                failures.append(str(refusal))
                return
            process_id = ask.get("process_id")
            launched = False
            if isinstance(process_id, int):
                with suppress(psutil.Error):
                    launched = any(parent.pid == os.getpid() for parent in psutil.Process(process_id).parents())
            holder.decide(str(ask["attendance_id"]), approve=launched)
            if launched and isinstance(process_id, int):
                approved.append(process_id)

    watcher = threading.Thread(target=attend, name="agent-live-attendance", daemon=True)
    watcher.start()
    try:
        yield approved
    finally:
        stop.set()
        watcher.join(timeout=5)
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


def run(programs: Programs, package: Path | None, scratch: Path, *, checkout: Path, model: str | None) -> Receipt:
    """Run both turns against a fresh root below ``scratch``."""
    receipt = Receipt()
    receipt.record("artifact", **package_identity(package))
    key = _anthropic_key(checkout)
    if key is None:
        receipt.unproven.append(f"live agent: no {_KEY_NAME} in {checkout / '.env'}")
        return receipt
    root, secret_store, workspace = scratch / "storage", scratch / "secrets", scratch / "workspace"
    secret_store.mkdir(parents=True)
    workspace.mkdir()
    environment = consumer_environment(root, secret_store)
    authority_root = os.environ.get("CADRUMO_AUTHORITY_ROOT")
    if package is None and authority_root is not None:
        # Source programs read the authority this checkout publishes; a package carries its own.
        environment["CADRUMO_AUTHORITY_ROOT"] = authority_root
    log = scratch / "processes.log"
    profile = create_profile(programs, environment, _PROFILE, log)
    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        receipt.record("runtime_ready", product_version=runtime.ready().get("product_version"))
        profile = identify_profile(programs, environment, profile, log)
        state_taxpayer(programs, environment, profile)
        holder = Holder(programs, environment, profile, log)
        try:
            holder.event("held")
            receipt.record("signed_in_and_held")
            with _attending(holder) as approved, _gateway(checkout, programs, environment, scratch, key) as gateway:
                chosen = gateway.model(workspace, model)
                receipt.record("gateway_ready", model=chosen)
                first, answer, tools, _ = gateway.turn(
                    workspace,
                    chosen,
                    "Use your Cadrumo tools to read my profile. Reply with the taxpayer's full name exactly as "
                    "the profile records it, and nothing else.",
                    None,
                )
                require(bool(tools), f"the agent called no Cadrumo tool: {answer!r}")
                require(_TAXPAYER.lower() in answer.lower(), f"the answer does not name the taxpayer: {answer!r}")
                receipt.record("read_through_tools", tools=tools, answer=answer.strip()[:200])
                before = _ledger_text(programs, environment, profile)
                require(_LEDGER_MARKER not in before, "the ledger already holds the acceptance row")
                _, answer, tools, approvals = gateway.turn(
                    workspace,
                    chosen,
                    "Use your Cadrumo tools to add one ledger expense: 12.34 EUR on 2026-01-15, description "
                    f"'{_LEDGER_MARKER}'. Use the ledger.add operation and add it exactly once.",
                    first,
                )
                after = _ledger_text(programs, environment, profile)
                require(
                    after.count(_LEDGER_MARKER) == 1, f"the ledger holds the row {after.count(_LEDGER_MARKER)} times"
                )
                receipt.record(
                    "wrote_through_tools", tools=tools, approvals=approvals, attended_processes=len(approved)
                )
            holder.close_input()
            reason, exit_code = holder.finish()
            require(reason == "input_closed" and exit_code == 0, f"holder: {reason} {exit_code}")
        finally:
            holder.stop()
        stopped = runtime.stop()
        require(stopped == 64, f"runtime exit: {stopped}")
        receipt.record("runtime_stopped", exit_code=stopped)
    survivors = started_processes()
    require(not survivors, f"processes this run started survive it: {survivors}")
    receipt.record("no_surviving_processes")
    return receipt


def main(arguments: list[str] | None = None) -> int:
    """Run the proof; exit 0 when every step held, 1 on a contradicted step, 3 when a step was left out."""
    parser = argparse.ArgumentParser(prog="agent-live", description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--package", type=Path, help="A built package directory.")
    target.add_argument(
        "--programs",
        type=Path,
        help="A directory holding aeat, cadrumo-runtime and cadrumo-mcp, such as a checkout's environment scripts.",
    )
    parser.add_argument(
        "--agent-checkout",
        type=Path,
        default=os.environ.get("CADRUMO_AGENT_CHECKOUT"),
        help="A cadrumo-agent checkout with its environment synced (default: $CADRUMO_AGENT_CHECKOUT).",
    )
    parser.add_argument("--model", default=None, help="A model id from the live catalog (default: its recommendation).")
    parser.add_argument("--keep", action="store_true", help="Keep the disposable root for inspection.")
    options = parser.parse_args(arguments)
    if options.agent_checkout is None:
        parser.error("give --agent-checkout or set CADRUMO_AGENT_CHECKOUT")
    package = None if options.package is None else Path(options.package).resolve(strict=True)
    programs = Programs.of(package) if package is not None else _source_programs(Path(options.programs))
    checkout = Path(options.agent_checkout).resolve(strict=True)
    base = _REPOSITORY_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="agent-live-", dir=base))
    try:
        receipt = run(programs, package, scratch, checkout=checkout, model=options.model)
    except (AcceptanceError, BaseExceptionGroup) as failure:
        reason = acceptance_failure(failure)
        if reason is None:
            raise
        print(json.dumps({"step": "failed", "reason": reason, "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    if receipt.unproven:
        print(json.dumps({"step": "incomplete", "unproven": receipt.unproven}), flush=True)
        return 3
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
