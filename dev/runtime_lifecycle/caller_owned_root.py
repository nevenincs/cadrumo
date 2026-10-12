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
4. signs out, closes the runtime's standard input and requires a drained exit;
5. requires the person's installed default storage root to be unchanged.

The profile password exists only in this process's memory and the CLI's
standard input. Run it with ``just verify-caller-owned-runtime PACKAGE``.
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

    def record(self, step: str, **facts: Any) -> None:
        """Append one step's facts and echo them for the operator."""
        entry = {"step": step, **facts}
        self.steps.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)


class AcceptanceError(AssertionError):
    """A step whose observed outcome contradicts the documented contract."""


def _require(condition: bool, message: str) -> None:
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


def _cli(
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
        envelope = json.loads(text.splitlines()[-1] if text else "{}")
    except ValueError:
        envelope = {"unparsed_output": True}
    return result.returncode, envelope if isinstance(envelope, dict) else {}


def _error_code(envelope: Mapping[str, Any]) -> str | None:
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
        _require(bool(lines) and bool(lines[0]), f"no readiness line; runtime exit {self.process.poll()}")
        announcement = json.loads(lines[0])
        _require(isinstance(announcement, dict), "readiness line is not a JSON object")
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
            private = await client.call_tool("observe", {"observation": {}})
    return {
        "status": status.structured_content,
        "status_error": status.is_error,
        "observe": private.structured_content,
        "observe_error": private.is_error,
    }


def _tree(root: Path) -> dict[str, tuple[int, int]]:
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
    before = _tree(default_root)
    receipt.record("default_root_observed", exists=default_root.exists(), entries=len(before))

    password = secrets.token_urlsafe(32)
    code, envelope = _cli(
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
    _require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile create: {code} {envelope}")
    receipt.record("profile_created", status=envelope.get("status"))

    code, envelope = _cli(
        programs, environment, "config", "login", _PROFILE_NAME, "--secrets-stdin", secret={"passphrase": password}
    )
    _require(_error_code(envelope) == "REFUSED_LOCAL_RUNTIME", f"login without a runtime: {code} {envelope}")
    receipt.record("login_refused_without_runtime", exit_code=code, code=_error_code(envelope))

    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        announcement = runtime.ready()
        _require(announcement.get("kind") == "runtime_ready", f"readiness: {announcement}")
        receipt.record(
            "runtime_ready",
            product_version=announcement.get("product_version"),
            storage_identity=announcement.get("storage_identity"),
        )

        code, envelope = _cli(programs, environment, "config", "sign-in-status")
        _require(code == 0, f"sign-in-status against the served root: {code} {envelope}")
        receipt.record("runtime_discovered", presence=envelope.get("result", {}).get("status", {}).get("presence"))

        code, envelope = _cli(
            programs, environment, "config", "login", _PROFILE_NAME, "--secrets-stdin", secret={"passphrase": password}
        )
        _require(code == 0 and envelope.get("status") in {"success", "warning"}, f"login: {code} {envelope}")
        receipt.record("login_authenticated", status=envelope.get("status"))

        code, envelope = _cli(programs, environment, "config", "profile", "status")
        _require(code == 0 and envelope.get("status") in {"success", "warning"}, f"profile status: {code} {envelope}")
        receipt.record("profile_read", status=envelope.get("status"))

        mcp = asyncio.run(_mcp_status(programs, environment, scratch))
        status = mcp["status"] or {}
        _require(status.get("profile_id") is not None, f"MCP did not reach the served root: {mcp}")
        receipt.record(
            "mcp_connected",
            authenticated=status.get("authenticated"),
            session=status.get("session"),
            denial=status.get("denial"),
            sign_in_reason=status.get("sign_in_reason"),
            observe=(mcp["observe"] or {}).get("outcome"),
            observe_code=(mcp["observe"] or {}).get("code"),
        )

        code, envelope = _cli(programs, environment, "config", "logout")
        receipt.record("logout", exit_code=code, status=envelope.get("status"), code=_error_code(envelope))
        exit_code = runtime.stop()
    _require(exit_code == _SUPERVISOR_STOP, f"runtime exit after input closed: {exit_code}")
    receipt.record("runtime_stopped", exit_code=exit_code)

    code, envelope = _cli(programs, environment, "config", "sign-in-status")
    _require(_error_code(envelope) == "REFUSED_LOCAL_RUNTIME", f"after stop: {code} {envelope}")
    receipt.record("runtime_gone", code=_error_code(envelope))

    after = _tree(default_root)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    _require(not changed, f"the installed default root changed: {changed[:20]}")
    receipt.record("default_root_unchanged", entries=len(after))
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
        run(options.package.resolve(strict=True), scratch)
    except AcceptanceError as failure:
        # A failed root is kept: its runtime log is the diagnosis.
        print(json.dumps({"step": "failed", "reason": str(failure), "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
