"""Accept a built package's caller-owned runtime on a disposable storage root.

This drives the package the way an external consumer does: only its programs
(``bin/aeat``, ``bin/cadrumo-runtime``, ``bin/cadrumo-mcp``) and its documented
environment, ``CADRUMO_LOCAL_STORAGE_ROOT`` and ``CADRUMO_SECRET_STORE_DIR``.
Nothing here imports the product to reach the runtime. The run:

1. creates a synthetic profile on a fresh root and shows that sign-in is
   refused while no runtime serves that root;
2. starts ``cadrumo-runtime --configured-root`` and waits for its readiness line;
3. signs in through the CLI's secret channel, reads the profile, and opens the
   packaged MCP server against the same root;
4. signs out, requires a new MCP process to be refused the profile read once a
   stored sign-in existed, closes the runtime's standard input and requires a
   drained exit;
5. requires the person's installed default storage root to be unchanged outside the
   checkouts' development roots, and free of anything this run created.

The profile password exists only in this process's memory and the CLI's
standard input. Run it with ``just verify-caller-owned-runtime PACKAGE``.

Exit 0 means every step held. Exit 1 names the contradicted step. Exit 3 means
every step that ran held, but the logon's native credential store refused the
stored sign-in, so MCP resume and logout could not be shown; run it again from
an interactive desktop logon.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.core.storage_environment import host_installed_default_root

_PROFILE_NAME = "caller-owned-acceptance"
_READY_SECONDS = 180
_COMMAND_SECONDS = 180
_STOP_SECONDS = 120
_SUPERVISOR_STOP = 64
# A registered read-only operation over the signed-in profile; tool discovery alone proves no access.
_PRIVATE_READ = "auth.local-read"
_DEVELOPMENT_ROOTS = ("storage", "development")


@dataclass(frozen=True, slots=True)
class Programs:
    """The packaged programs a consumer starts."""

    aeat: Path
    runtime: Path
    mcp: Path

    @classmethod
    def of(cls, package: Path) -> Programs:
        """Locate the three entry points in a package's ``bin`` directory."""
        suffix = ".exe" if sys.platform == "win32" else ""
        names = ("aeat", "cadrumo-runtime", "cadrumo-mcp")
        paths = [(package / "bin" / f"{name}{suffix}").resolve(strict=True) for name in names]
        return cls(*paths)


@dataclass(slots=True)
class Receipt:
    """Credential-free facts of one acceptance run."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    unproven: list[str] = field(default_factory=list)

    def record(self, step: str, **facts: Any) -> None:
        """Append one step's facts and echo them for the operator."""
        entry = {"step": step, **facts}
        self.steps.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)


class AcceptanceError(AssertionError):
    """A step whose observed outcome contradicts the documented contract."""


def require(condition: bool, message: str) -> None:
    """Fail the acceptance with ``message`` unless ``condition`` holds."""
    if not condition:
        raise AcceptanceError(message)


def consumer_environment(root: Path, secret_store: Path) -> dict[str, str]:
    """Return the ambient environment without product or interpreter settings, plus the two pins."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith(("CADRUMO_", "PYTHON", "VIRTUAL_ENV", "UV_"))
    }
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    environment["CADRUMO_SECRET_STORE_DIR"] = str(secret_store)
    return environment


def run_cli(
    programs: Programs, environment: Mapping[str, str], *arguments: str, secret: Mapping[str, str] | None = None
) -> tuple[int, dict[str, Any]]:
    """Run one JSON CLI command; a secret travels only on standard input."""
    result = subprocess.run(  # noqa: S603 -- exact packaged executable; no shell; secrets only on stdin.
        [str(programs.aeat), "--format", "json", *arguments],
        input=json.dumps(secret) if secret is not None else "",
        env=dict(environment),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=_COMMAND_SECONDS,
        check=False,
    )
    text = result.stdout.strip() or result.stderr.strip()
    try:
        envelope = json.loads(text or "{}")
    except ValueError:
        envelope = {"unparsed_output": True}
    return result.returncode, envelope if isinstance(envelope, dict) else {}


def notice_codes(envelope: Mapping[str, Any]) -> list[str]:
    """Return the codes of an envelope's notices."""
    notices = envelope.get("notices")
    if not isinstance(notices, list):
        return []
    return [str(notice.get("code")) for notice in notices if isinstance(notice, dict)]


def error_code(envelope: Mapping[str, Any]) -> str | None:
    """Return an error envelope's code, or ``None`` when it carries none."""
    error = envelope.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


@contextmanager
def caller_owned_runtime(programs: Programs, environment: Mapping[str, str], log: Path) -> Iterator[RuntimeProcess]:
    """Start the runtime with piped standard streams; always end it by closing its input first."""
    with log.open("wb") as errors:
        process = subprocess.Popen(  # noqa: S603 -- exact packaged executable; no shell.
            [str(programs.runtime), "--configured-root"],
            env=dict(environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        owned = RuntimeProcess(process)
        try:
            yield owned
        finally:
            owned.stop()


@dataclass(slots=True)
class RuntimeProcess:
    """One caller-owned runtime and the exit it settled with."""

    process: subprocess.Popen[bytes]
    exit_code: int | None = None

    def ready(self) -> dict[str, Any]:
        """Return the readiness line, or fail when none arrives in time."""
        output = self.process.stdout
        if output is None:
            raise AcceptanceError("runtime standard output was not piped")
        lines: list[bytes] = []
        reader = threading.Thread(target=lambda: lines.append(output.readline()), daemon=True)
        reader.start()
        reader.join(_READY_SECONDS)
        require(bool(lines) and bool(lines[0]), f"no readiness line; runtime exit {self.process.poll()}")
        announcement = json.loads(lines[0])
        require(isinstance(announcement, dict), "readiness line is not a JSON object")
        return announcement

    def stop(self) -> int:
        """Close standard input, wait for the drain, and kill only a runtime that ignores it."""
        if self.exit_code is not None:
            return self.exit_code
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.exit_code = self.process.wait(timeout=_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.exit_code = self.process.wait(timeout=_STOP_SECONDS)
            raise AcceptanceError("the runtime did not stop after its standard input closed") from None
        return self.exit_code


async def _mcp_status(programs: Programs, environment: Mapping[str, str], directory: Path) -> dict[str, Any]:
    server = StdioServerParameters(command=str(programs.mcp), args=[], env=dict(environment), cwd=directory)
    with open(os.devnull, "w", encoding="utf-8") as errors:
        async with (
            stdio_client(server, errlog=errors) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream, read_timeout_seconds=_COMMAND_SECONDS) as client,
        ):
            await client.initialize()
            status = await client.call_tool("status", {})
            read = await _private_read(client, _status_view(status.structured_content or {})["profile_id"])
    return {"status": status.structured_content, "status_error": status.is_error, "read": read}


def _status_view(status: Mapping[str, Any]) -> dict[str, Any]:
    """Read the MCP status reply in either shape: unauthenticated, or a held session with its access status."""
    held = status.get("status")
    if not isinstance(held, dict):
        return {
            "profile_id": status.get("profile_id"),
            "authenticated": status.get("authenticated"),
            "denial": status.get("denial"),
        }
    # A held session's lease is live only while the runtime reports no denial for it.
    return {
        "profile_id": held.get("profile_id"),
        "authenticated": status.get("session") not in {None, "none"} and held.get("denial") is None,
        "denial": held.get("denial"),
    }


async def _private_read(client: ClientSession, profile_id: str | None) -> dict[str, Any]:
    """Run one registered profile read and wait for its result; only outcome codes are kept."""
    payload = {"kind": "status", "profile_id": profile_id}
    executed = await client.call_tool("execute", {"definition_id": _PRIVATE_READ, "payload": payload})
    submitted = executed.structured_content or {}
    facts: dict[str, Any] = {
        "execute": submitted.get("outcome"),
        "execute_code": submitted.get("code"),
        "execute_faults": submitted.get("faults"),
        "answered": False,
    }
    receipt = submitted.get("receipt")
    if executed.is_error or submitted.get("outcome") != "submitted" or not isinstance(receipt, dict):
        return facts
    deadline = asyncio.get_running_loop().time() + _COMMAND_SECONDS
    while True:
        answer = await client.call_tool("result", {"result": {"operation_id": receipt.get("operation_id")}})
        document = answer.structured_content or {}
        facts.update(result=document.get("outcome"), result_code=document.get("code"))
        if not answer.is_error and document.get("outcome") == "reply" and "error_detail" not in document:
            facts["answered"] = True
            return facts
        if asyncio.get_running_loop().time() >= deadline:
            return facts
        await asyncio.sleep(1)


def _mcp_facts(mcp: Mapping[str, Any]) -> dict[str, Any]:
    """Return the credential-free facts of one MCP connection, without the granted scope listing."""
    status = mcp["status"] or {}
    return {
        **_status_view(status),
        "session": status.get("session"),
        "sign_in_reason": status.get("sign_in_reason"),
        **mcp["read"],
    }


def file_facts(root: Path) -> dict[str, tuple[int, int]]:
    """Return every entry's size and modification time below ``root``; empty when absent."""
    if not root.exists():
        return {}
    facts: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        try:
            metadata = path.lstat()
        except OSError:
            continue
        facts[str(path.relative_to(root))] = (metadata.st_size, metadata.st_mtime_ns)
    return facts


def run(package: Path, scratch: Path) -> Receipt:
    """Execute the acceptance on a fresh root below ``scratch``."""
    receipt = Receipt()
    programs = Programs.of(package)
    root, secret_store = scratch / "storage", scratch / "secrets"
    secret_store.mkdir(parents=True)
    environment = consumer_environment(root, secret_store)
    default_root = host_installed_default_root(os.environ)
    before = file_facts(default_root)
    receipt.record("default_root_observed", exists=default_root.exists(), entries=len(before))

    password = secrets.token_urlsafe(32)
    code, envelope = run_cli(
        programs,
        environment,
        "config",
        "profile",
        "create",
        _PROFILE_NAME,
        "--quiet",
        "--secrets-stdin",
        secret={"passphrase": password, "passphrase_confirmation": password},
    )
    require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile create: {code} {envelope}")
    receipt.record("profile_created", status=envelope.get("status"))

    code, envelope = run_cli(
        programs, environment, "config", "login", _PROFILE_NAME, "--secrets-stdin", secret={"passphrase": password}
    )
    require(error_code(envelope) == "REFUSED_LOCAL_RUNTIME", f"login without a runtime: {code} {envelope}")
    receipt.record("login_refused_without_runtime", exit_code=code, code=error_code(envelope))

    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        announcement = runtime.ready()
        require(announcement.get("kind") == "runtime_ready", f"readiness: {announcement}")
        receipt.record(
            "runtime_ready",
            product_version=announcement.get("product_version"),
            storage_identity=announcement.get("storage_identity"),
        )

        code, envelope = run_cli(programs, environment, "config", "sign-in-status")
        require(code == 0, f"sign-in-status against the served root: {code} {envelope}")
        receipt.record("runtime_discovered", presence=envelope.get("result", {}).get("status", {}).get("presence"))

        code, envelope = run_cli(
            programs, environment, "config", "login", _PROFILE_NAME, "--secrets-stdin", secret={"passphrase": password}
        )
        require(code == 0 and envelope.get("status") in {"success", "warning"}, f"login: {code} {envelope}")
        notices = notice_codes(envelope)
        persisted = envelope.get("result", {}).get("session_persisted") is True
        require(
            persisted is ("config.login.session_not_persisted" not in notices),
            f"session_persisted disagrees with the login notices: {envelope}",
        )
        receipt.record("login_authenticated", status=envelope.get("status"), persisted=persisted, notices=notices)
        if not persisted:
            # MCP follows only a stored sign-in, and logout checks it; this logon's credential store refused it.
            receipt.unproven.append("stored sign-in: MCP resume and logout need a working native credential store")

        # A piped command names its own credential channel; it never borrows the stored sign-in.
        code, envelope = run_cli(
            programs,
            environment,
            "--profile-secrets-stdin",
            "config",
            "profile",
            "status",
            secret={"profile_passphrase": password},
        )
        require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile status: {code} {envelope}")
        receipt.record("profile_read", status=envelope.get("status"))

        mcp = asyncio.run(_mcp_status(programs, environment, scratch))
        connected = _mcp_facts(mcp)
        require(connected["profile_id"] is not None, f"MCP did not reach the served root: {connected}")
        receipt.record("mcp_connected", **connected)

        if persisted:
            # Discovery alone proves nothing: a registered read of the profile must be answered.
            require(
                connected["authenticated"] is True and connected["answered"],
                f"MCP did not follow the stored sign-in: {connected}",
            )
        else:
            require(connected["denial"] == "authentication_required", f"MCP without a stored sign-in: {connected}")
        code, envelope = run_cli(programs, environment, "config", "logout")
        error = envelope.get("error")
        receipt.record(
            "logout",
            exit_code=code,
            status=envelope.get("status"),
            code=error_code(envelope),
            message=error.get("message") if isinstance(error, dict) else None,
        )
        require(code == 0 or not persisted, f"logout: {code} {envelope}")
        if persisted:
            # A new MCP process after sign-out must find nothing to follow.
            after_logout = asyncio.run(_mcp_status(programs, environment, scratch))
            refused = _mcp_facts(after_logout)
            receipt.record("mcp_after_logout", **refused)
            require(
                refused["authenticated"] is not True and not refused["answered"],
                f"MCP still read the profile after sign-out: {refused}",
            )
        exit_code = runtime.stop()
    require(exit_code == _SUPERVISOR_STOP, f"runtime exit after input closed: {exit_code}")
    receipt.record("runtime_stopped", exit_code=exit_code)

    code, envelope = run_cli(programs, environment, "config", "sign-in-status")
    require(error_code(envelope) == "REFUSED_LOCAL_RUNTIME", f"after stop: {code} {envelope}")
    receipt.record("runtime_gone", code=error_code(envelope))

    after = file_facts(default_root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    # Checkouts' own development roots live below the default root, and other builds and test runs on this
    # host write there while this runs. Only what this run created can be attributed to it there.
    development = [name for name in changed if Path(name).parts[:2] == _DEVELOPMENT_ROOTS]
    ours = {path.name for path in (root / "buckets").iterdir()} if (root / "buckets").is_dir() else set()
    leaked = [name for name in changed if name not in development or ours.intersection(Path(name).parts)]
    require(not leaked, f"the installed default root changed: {leaked[:20]}")
    receipt.record("default_root_unchanged", entries=len(after), development_roots_changed=len(development))
    return receipt


def main(arguments: list[str] | None = None) -> int:
    """Run the acceptance; exit nonzero on any contradicted step."""
    parser = argparse.ArgumentParser(prog="caller-owned-root", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--package", required=True, type=Path, help="A built package directory, such as stage/<config>/app."
    )
    parser.add_argument("--keep", action="store_true", help="Keep the disposable root for inspection.")
    options = parser.parse_args(arguments)
    scratch = Path(tempfile.mkdtemp(prefix="cadrumo-co-"))
    try:
        receipt = run(options.package.resolve(strict=True), scratch)
    except AcceptanceError as failure:
        # A failed root is kept: its runtime log is the diagnosis.
        print(json.dumps({"step": "failed", "reason": str(failure), "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    if receipt.unproven:
        # Everything that ran held; the listed parts could not run on this logon.
        print(json.dumps({"step": "incomplete", "unproven": receipt.unproven}), flush=True)
        return 3
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
