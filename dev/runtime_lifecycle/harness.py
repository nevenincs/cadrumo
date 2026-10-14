"""Process-owned manager acceptance using real native transport and authentication."""

from __future__ import annotations

import json
import secrets
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from cadrumo.adapters.local_runtime.boot_record import RuntimeBootRecord, read_runtime_boot_record
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_channel import WindowsRuntimeChannel
from cadrumo.adapters.local_runtime.windows_native_io import owned_windows_handle
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess, WindowsProcessScope
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.domain.calculations.registry.authority_location import published_authority_generation
from dev.packaging.command_execution import run_command

_REVEAL_IDENTIFIERS = "CADRUMO_CLI_REVEAL_IDENTIFIERS"
"""The command line's operator opt-in to print the identifiers its output otherwise hides."""


@dataclass(frozen=True, repr=False)
class Profile:
    """Synthetic profile coordinates with an undisclosed random password."""

    profile_id: UUID
    password: str = field(repr=False)


@dataclass
class Connection:
    """Retain the frontend, wire and kernel-verified peer together."""

    client: RuntimeFrontendClient
    wire: VerifiedRuntimeConnection
    native: WindowsRuntimeChannel


class LifecycleHarness:
    """Retain one isolated root, kill-on-close job, and all native connections."""

    def __init__(self, manager: Path, package: Path, root: Path) -> None:
        """Bind explicit binaries and a not-yet-created test storage directory."""
        self.manager, self.package, self.root = manager, package, root
        self.runtime_image = package / "bin/cadrumo-runtime.exe"
        self.cli_image = package / "bin/aeat.exe"
        self.resources = ExitStack()
        self.metrics: dict[str, float] = {}
        self.started = 0.0
        self._manager_crashed = False
        self.retain_profile_receipts = False
        self.endpoint: WindowsRuntimeEndpoint
        self.process: WindowsOwnedProcess
        self.scope: WindowsProcessScope

    def __enter__(self) -> LifecycleHarness:
        """Launch a job-contained driver without a desktop-context prerequisite."""
        if sys.platform != "win32":
            raise RuntimeError("Lifecycle acceptance requires Windows native IPC")
        for path in (self.manager, self.runtime_image, self.cli_image, self.package / "data/package-manifest.json"):
            if not path.is_file():
                raise RuntimeError("A complete package and debug lifecycle driver are required")
        self.root.mkdir()
        (self.root / "lifecycle-owned-root").write_bytes(b"cadrumo-process-lifecycle-v1\n")
        try:
            self.endpoint = WindowsRuntimeEndpoint(storage_root=self.root)
            self.resources.callback(self.endpoint.close)
            scope = WindowsProcessScope()
            self.scope = scope
            self.resources.callback(scope.terminate, timeout=15)
            self.started = time.monotonic()
            self.start_manager()
            return self
        except BaseException:
            self.resources.close()
            raise

    def __exit__(self, *_exc: object) -> None:
        """Stop the manager and reap its entire test job, even after a failure."""
        started = time.monotonic()
        try:
            self.stop_manager()
        finally:
            self.resources.close()
            self.metrics["cleanup_seconds"] = time.monotonic() - started

    def stop_manager(self) -> None:
        """Request the existing manager stop path and prove its settled exit."""
        if self._manager_crashed:
            if self.process.wait(timeout=0) != 73:
                raise RuntimeError("Manager crash exit changed")
            return
        (self.root / "manager-stop").touch()
        code = self.process.wait(timeout=35)
        if code != 0:
            raise RuntimeError(f"Native manager lifecycle driver failed: exit {code}")

    def start_manager(self) -> None:
        """Explicitly launch a supervisor; external clients never do this."""
        self.process = self.scope.launch(
            executable=self.manager,
            arguments=(str(self.package), str(self.root)),
            directory=self.root,
            environment=child_environment(ChildEnvironmentProfile.STRICT, self.root),
        )
        self._manager_crashed = False

    def terminate_manager(self) -> None:
        """Kill the exact child whose retained process handle prevents PID reuse."""
        import win32api
        import win32con
        import win32process

        # A retained child handle pins this PID until the test Job closes it.
        handle = owned_windows_handle(
            win32api.OpenProcess(
                win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                False,
                self.process.pid,
            )
        )
        try:
            if not self.scope.contains_process(int(handle)):
                raise RuntimeError("Manager is outside the test-owned process job")
            win32process.TerminateProcess(int(handle), 73)
            if self.process.wait(timeout=10) != 73:
                raise RuntimeError("Exact manager termination was not confirmed")
            self._manager_crashed = True
        finally:
            handle.Close()

    def connect(
        self,
        profile_id: UUID,
        *,
        timeout: float = 90,
        after_boot: UUID | None = None,
        lifecycle_notices: Literal["v1"] | None = None,
    ) -> Connection:
        """Await verified readiness, optionally negotiating canonical lifecycle notices."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                native = self.endpoint.connect(
                    timeout=min(0.2, max(0.001, deadline - time.monotonic())), expected_image=self.runtime_image
                )
                wire = VerifiedRuntimeConnection(
                    native,
                    expected=RuntimeClientHello(
                        product_version=version("cadrumo"),
                        storage_identity=self.endpoint.storage_identity,
                        authority_generation=published_authority_generation(),
                        lifecycle_notices=lifecycle_notices,
                    ),
                    deadline=deadline,
                )
                if after_boot is None or wire.hello.boot_id != after_boot:
                    client = RuntimeFrontendClient(
                        wire, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                    )
                    self.resources.callback(client.close)
                    return Connection(client, wire, native)
                wire.close()
            except RuntimeRefusalError as error:
                if error.reason not in {RuntimeRefusalCode.ENDPOINT_NOT_READY, RuntimeRefusalCode.CONNECTION_CLOSED}:
                    raise
            try:
                code = self.process.wait(timeout=0)
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
            else:
                raise RuntimeError(f"Manager exited before verified readiness: {code}")
            if time.monotonic() >= deadline:
                raise TimeoutError("Manager did not provide verified runtime readiness")
            time.sleep(0.05)

    def cli(
        self,
        *arguments: str,
        secret: dict[str, str] | None = None,
        profile_secret: str | None = None,
        expect_success: bool = True,
        reveal_identifiers: bool = False,
    ) -> dict[str, Any]:
        """Invoke the package CLI with secrets on stdin and bounded process wait.

        Command output hides identifiers. ``reveal_identifiers`` sets the operator's
        opt-in the package admits for the command line, for a result whose identifier
        the caller must use, such as the reference an agent is launched with.
        """
        if secret is not None and profile_secret is not None:
            raise ValueError("CLI leaf and root profile secret inputs cannot share stdin")
        profile_arguments = () if profile_secret is None else ("--profile-secrets-stdin",)
        if profile_secret is not None:
            secret = {"profile_passphrase": profile_secret}
        environment = child_environment(ChildEnvironmentProfile.STRICT, self.root)
        if reveal_identifiers:
            environment[_REVEAL_IDENTIFIERS] = "1"
        payload = None if secret is None else bytearray(json.dumps(secret), "utf-8")
        try:
            result = run_command(
                [str(self.cli_image), "--format", "json", *profile_arguments, "config", *arguments],
                environment=environment,
                cwd=self.root,
                input_text=None if payload is None else payload.decode("utf-8"),
                timeout_seconds=90,
            )
        finally:
            if payload is not None:
                payload[:] = bytes(len(payload))
        document = json.loads(result.stdout if result.returncode == 0 else result.stderr)
        if expect_success and result.returncode != 0:
            detail = document.get("error")
            code = detail.get("code") if isinstance(detail, dict) else None
            raise RuntimeError(f"Lifecycle CLI command failed: exit {result.returncode}, code={code!r}")
        if expect_success and document.get("status") not in {"success", "warning"}:
            raise RuntimeError(f"Lifecycle CLI envelope status: {document.get('status')!r}")
        if not expect_success and (result.returncode == 0 or document.get("status") in {"success", "warning"}):
            raise AssertionError("Protected CLI call unexpectedly succeeded")
        if not expect_success and (
            not isinstance(document.get("error"), dict) or not isinstance(document["error"].get("code"), str)
        ):
            raise AssertionError("Protected CLI call returned no typed refusal")
        return document

    def create_profile(self, name: str) -> Profile:
        """Create through the real CLI and retain keychain cleanup ownership."""
        password = f"Lifecycle-{secrets.token_urlsafe(24)}!"
        self.cli(
            "profile",
            "create",
            name,
            "--quiet",
            "--secrets-stdin",
            secret={
                "passphrase": password,
                "passphrase_confirmation": password,
            },
        )
        selected = observe_active_profile_pointer(self.root).bucket_id
        if selected is None:
            raise RuntimeError("Profile creation did not select its committed profile")
        profile_id = UUID(selected)
        if not self.retain_profile_receipts:
            self.resources.callback(delete_profile_session, storage_root=self.root, profile_id=profile_id)
        return Profile(profile_id, password)

    def terminate_runtime(self, connection: Connection) -> RuntimeBootRecord:
        """Kill only the native incarnation already verified by this live connection."""
        import win32api
        import win32con
        import win32event
        import win32process

        record = read_runtime_boot_record(storage_root=self.root)
        if not isinstance(record, RuntimeBootRecord) or record.boot_id != connection.wire.hello.boot_id:
            raise RuntimeError("No matching supervised boot record")
        if record.pid != connection.native.peer.process_id:
            raise RuntimeError("Boot record does not name the verified peer")
        handle = owned_windows_handle(
            win32api.OpenProcess(
                win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                False,
                record.pid,
            )
        )
        try:
            # Compare retained kernel handles, including birth times, before the kill.
            connection.native.verify_peer_process(int(handle))
            if not self.owns_runtime(connection, int(handle)):
                raise RuntimeError("Verified runtime is outside the test-owned process job")
            win32process.TerminateProcess(int(handle), 73)
            if win32event.WaitForSingleObject(int(handle), 10_000) != win32event.WAIT_OBJECT_0:
                raise RuntimeError("Exact runtime termination was not confirmed")
        finally:
            handle.Close()
        return record

    def owns_runtime(self, connection: Connection, handle: int) -> bool:
        """Require the driver-owned test job before any runtime termination."""
        return self.scope.contains_process(handle)

    def events(self) -> list[dict[str, Any]]:
        """Read complete nonsecret supervisor events, ignoring a partial final write."""
        path = self.root / "manager-events.jsonl"
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        events = [json.loads(line) for line in lines if line.endswith("\n")]
        previous = 0
        terminal = False
        for event in events:
            if terminal:
                raise RuntimeError("Native lifecycle facts continue after the terminal driver failure")
            if isinstance(event, dict) and event.get("kind") == "driver_failed":
                if "sequence" in event:
                    raise RuntimeError("Terminal driver failure must not invent a canonical sequence")
                terminal = True
                continue
            sequence = event.get("sequence") if isinstance(event, dict) else None
            if type(sequence) is not int or not previous < sequence <= 2**64 - 1:
                raise RuntimeError("Native lifecycle facts lack a strictly increasing canonical sequence")
            previous = sequence
        return events
