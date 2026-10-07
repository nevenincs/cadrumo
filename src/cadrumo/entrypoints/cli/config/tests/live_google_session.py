"""Opt-in session-owned live CLI runner; real custody/client, no test overrides.

Uses the isolated synthetic profile handed off by Session 02. Its password stays
in DPAPI and the approved anonymous descriptor channel. Never run under pytest.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
import runpy
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient


class _TuiAcceptanceEvidence(Protocol):
    """The acceptance helper returns a nonsecret evidence document."""

    def to_dict(self) -> dict[str, object]:
        """Render the public acceptance evidence."""
        ...


class _TuiAcceptanceRunner(Protocol):
    """Exact runner-owned lease and selected saved work handed to the helper."""

    def __call__(
        self,
        client: RuntimeFrontendClient,
        *,
        work_unit_id: str,
        calculation_revision_id: str,
        profile_label: str,
        output_dir: Path,
        workspace_root: Path,
    ) -> Awaitable[_TuiAcceptanceEvidence]:
        """Drive the explicitly authorized TUI publication acceptance."""
        ...


def _load_worktree_tui_acceptance(workspace: Path) -> _TuiAcceptanceRunner:
    """Load the exact checkout helper even when the desktop starts elsewhere.

    ``runpy`` does not put the checkout on ``sys.path``. Loading this one
    reviewed source file avoids borrowing an unrelated installed ``dev``
    package or changing the native product's import search path.
    """
    workspace = workspace.resolve()
    source = (workspace / "dev/acceptance/review/installed_google_review_tui.py").resolve()
    if not source.is_relative_to(workspace) or not source.is_file():
        raise RuntimeError("the checked-in TUI acceptance helper is unavailable")
    name = "_cadrumo_worktree_google_review_tui_acceptance"
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("the checked-in TUI acceptance helper cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    # Dataclass annotation resolution requires the executing module to be
    # registered. This affects only this helper's unique private module name.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    entrypoint = getattr(module, "run_google_saved_review_tui", None)
    if not inspect.iscoroutinefunction(entrypoint):
        raise RuntimeError("the checked-in TUI acceptance helper has no async entrypoint")
    return cast(_TuiAcceptanceRunner, entrypoint)


async def _recover_exact_failed_tui_review(client: RuntimeFrontendClient) -> dict[str, object]:
    """Recover only this known untouched synthetic acceptance review, never Apply."""
    from uuid import uuid4

    from cadrumo.application.operations.frontend_projection import OperationReviewAvailableInteractionV1
    from cadrumo.application.operations.frontend_requests import (
        OperationObservationRequestV1,
        OperationObservationSuccessV1,
    )
    from cadrumo.application.runtime.operation_access import (
        RuntimeOperationAcknowledged,
        RuntimeOperationControl,
        RuntimeOperationObserve,
        RuntimeOperationObserved,
    )
    from cadrumo.core.operations import (
        OperationEffect,
        OperationLifecycle,
        OperationTerminalCondition,
        profile_operation_subject,
    )

    operation_id = "a828d9899c3b202b4aa5606fada669b8ea4858677b98f5d6c8af7b767d9e2f7a"
    deadline = time.monotonic() + 90

    async def observe():
        reply = await asyncio.to_thread(
            client.operation,
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=client.profile_id,
                session_id=client.session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
            ),
            deadline=deadline,
        )
        if not isinstance(reply, RuntimeOperationObserved) or not isinstance(
            reply.observation, OperationObservationSuccessV1
        ):
            raise RuntimeError("exact acceptance recovery could not observe its operation")
        state = reply.observation.projection
        if (
            state.operation_id != operation_id
            or state.definition_id != "export.google-review"
            or state.subject_ref != profile_operation_subject(str(client.profile_id))
            or state.effect is not OperationEffect.NONE
        ):
            raise RuntimeError("exact acceptance recovery refused foreign or effectful work")
        return state

    before = await observe()
    if before.lifecycle is not OperationLifecycle.TERMINAL:
        if before.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION or not isinstance(
            before.pending_interaction, OperationReviewAvailableInteractionV1
        ):
            raise RuntimeError("exact acceptance recovery requires an unconsumed human review")
        reply = await asyncio.to_thread(
            client.operation,
            RuntimeOperationControl(
                action="operation_resume",
                request_id=uuid4(),
                profile_id=client.profile_id,
                session_id=client.session_id,
                operation_id=operation_id,
            ),
            deadline=deadline,
        )
        if not isinstance(reply, RuntimeOperationAcknowledged) or reply.operation_id != operation_id:
            raise RuntimeError("exact acceptance recovery did not acknowledge its operation")
    while True:
        state = await observe()
        if state.lifecycle is OperationLifecycle.TERMINAL:
            if state.terminal_condition is not OperationTerminalCondition.REFUSED:
                raise RuntimeError("exact acceptance recovery did not settle the lost response authority")
            return {
                "recovered_operation_id": operation_id,
                "terminal_condition": state.terminal_condition.value,
                "effect": state.effect.value,
                "apply_requested": False,
            }
        if time.monotonic() >= deadline:
            raise RuntimeError("exact acceptance recovery did not settle within its bound")
        await asyncio.sleep(0.2)


def main() -> None:
    if sys.platform != "win32":
        raise RuntimeError("this live runner requires the Windows desktop")
    print(json.dumps({"stage": "starting", "terminal": sys.stdin.isatty()}), flush=True)
    workspace = Path(__file__).resolve().parents[6]
    root = workspace / "var/storage/session02-google-live"
    private = root / "session01-driver"
    private.mkdir(exist_ok=True)
    os.environ.update(
        {
            "CADRUMO_AUTHORITY_ROOT": str(workspace / ".authority"),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_DIR": str(root / "secrets"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_LOG_DIR": str(root / "logs"),
        }
    )
    os.environ.pop("CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE", None)
    import msvcrt

    import win32api
    import win32crypt
    import win32job

    from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
    from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
    from cadrumo.application.runtime.contracts import RuntimeClientHello
    from cadrumo.domain.calculations.registry.authority import published_authority_generation

    mode = sys.argv[1]
    commands = {
        "status": ["config", "google", "status"],
        "oauth": ["config", "google", "login"],
        "probe": ["config", "google", "probe", "--read-only"],
        "probe-write": ["config", "google", "probe"],
        "folder": ["config", "google", "folder", "view"],
        "archive-dry": [
            "config",
            "profile",
            "archive",
            "push",
            "--namespace",
            "cadrumo.google.drive.config",
            "--dry-run",
        ],
        "archive": ["config", "profile", "archive", "push", "--namespace", "cadrumo.google.drive.config"],
    }
    if mode not in {
        *commands,
        "resume",
        "reconcile",
        "organize",
        "review",
        "export-acceptance",
        "tui-acceptance",
        "cancel-review-acceptance",
        "diagnose",
    }:
        raise ValueError("unsupported live acceptance mode")
    if mode in {"oauth", "resume"} and not sys.stdin.isatty():
        raise RuntimeError("OAuth requires the real controlling terminal")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    job = win32job.CreateJobObject(None, "")
    limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
    with (private / "runtime.log").open("ab") as log:
        log_offset = log.tell()
        process = subprocess.Popen(  # noqa: S603 -- exact supported runtime path and fixed arguments; no shell.
            [
                str(workspace / ".venv/Scripts/cadrumo-runtime.exe"),
                "--storage-root",
                str(root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                "0.5.1",
                "--supervised",
            ],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
            creationflags=0x08000000,  # Windows CREATE_NO_WINDOW; runtime is supervised through pipes.
        )
        try:
            process_handle = win32api.OpenProcess(0x0101, False, process.pid)
            try:
                win32job.AssignProcessToJobObject(job, process_handle)
            finally:
                process_handle.Close()
            ready = False
            readiness_deadline = time.monotonic() + 600
            while time.monotonic() < readiness_deadline:
                if process.poll() is not None:
                    break
                try:
                    connection = asyncio.run(
                        RuntimeLaunchDoor(
                            endpoint,
                            expected=RuntimeClientHello(
                                product_version="0.5.1",
                                storage_identity=endpoint.storage_identity,
                                authority_generation=published_authority_generation(),
                            ),
                        ).open(timeout=2)
                    )
                except Exception:
                    time.sleep(0.5)
                else:
                    observed_boot = str(connection.hello.boot_id)
                    connection.close()
                    # Another developer may own this storage endpoint. A valid
                    # handshake alone does not make that runtime ours to use.
                    with (private / "runtime.log").open("rb") as owned_log:
                        owned_log.seek(log_offset)
                        records = owned_log.read().decode("utf-8").splitlines()
                    owned_boots = set()
                    for line in records:
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(record, dict) and record.get("type") == "ready":
                            owned_boots.add(record.get("boot_id"))
                    if observed_boot not in owned_boots:
                        time.sleep(0.5)
                        continue
                    ready = True
                    break
            print(json.dumps({"stage": "runtime", "ready": ready, "terminal": sys.stdin.isatty()}), flush=True)
            if not ready:
                raise RuntimeError("runtime readiness failed")
            if mode == "diagnose":
                import traceback
                from uuid import UUID

                from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
                from cadrumo.application.operations.registry import OperationFrontendProjection
                from cadrumo.application.user_profile.login_session import resolve_login_target
                from cadrumo.entrypoints.adapter_composition import profile_free_adapter_composition

                with profile_free_adapter_composition():
                    profile_id = UUID(resolve_login_target("Session02 Google Review").bucket_id)
                client = asyncio.run(
                    RuntimeFrontendClient.open(
                        RuntimeLaunchDoor(
                            endpoint,
                            expected=RuntimeClientHello(
                                product_version="0.5.1",
                                storage_identity=endpoint.storage_identity,
                                authority_generation=published_authority_generation(),
                            ),
                        ),
                        profile_id=profile_id,
                        frontend=OperationFrontendProjection.CLI,
                    )
                )
                try:
                    protected = bytearray(
                        win32crypt.CryptUnprotectData(
                            (root / "session02-driver/synthetic-profile-input.dpapi").read_bytes(),
                            None,
                            None,
                            None,
                            0,
                        )[1]
                    )
                    client.login_password(protected, persist_receipt=False)
                    print(json.dumps({"stage": "diagnose", "authenticated": client.session_id is not None}), flush=True)
                except Exception as failure:
                    chain = []
                    while failure is not None:
                        chain.append(
                            {
                                "type": type(failure).__name__,
                                "frames": [
                                    f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                                    for frame in traceback.extract_tb(failure.__traceback__)
                                ],
                            }
                        )
                        failure = failure.__cause__ or failure.__context__
                    print(json.dumps({"stage": "diagnose", "failures": chain}), flush=True)
                finally:
                    client.close()
                return
            if mode == "export-acceptance":
                from cadrumo.entrypoints.cli.config.tests.live_export_acceptance import run_live_export_acceptance

                print(json.dumps(run_live_export_acceptance(workspace, root)), flush=True)
                return
            if mode in {"tui-acceptance", "cancel-review-acceptance"}:
                from uuid import UUID

                from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
                from cadrumo.application.operations.registry import OperationFrontendProjection
                from cadrumo.application.user_profile.login_session import resolve_login_target
                from cadrumo.entrypoints.adapter_composition import profile_free_adapter_composition

                run_google_saved_review_tui = _load_worktree_tui_acceptance(workspace)
                journal = json.loads((root / "logs/live-export-acceptance/acceptance-journal.json").read_text())
                with profile_free_adapter_composition():
                    profile_id = UUID(resolve_login_target("Session02 Google Review").bucket_id)

                async def run_tui() -> dict[str, object]:
                    client = await RuntimeFrontendClient.open(
                        RuntimeLaunchDoor(
                            endpoint,
                            expected=RuntimeClientHello(
                                product_version="0.5.1",
                                storage_identity=endpoint.storage_identity,
                                authority_generation=published_authority_generation(),
                            ),
                        ),
                        profile_id=profile_id,
                        frontend=OperationFrontendProjection.TUI
                        if mode == "tui-acceptance"
                        else OperationFrontendProjection.CLI,
                    )
                    async with client:
                        protected = bytearray(
                            win32crypt.CryptUnprotectData(
                                (root / "session02-driver/synthetic-profile-input.dpapi").read_bytes(),
                                None,
                                None,
                                None,
                                0,
                            )[1]
                        )
                        await asyncio.to_thread(client.login_password, protected, persist_receipt=False)
                        if mode == "cancel-review-acceptance":
                            return await _recover_exact_failed_tui_review(client)
                        evidence = await run_google_saved_review_tui(
                            client,
                            work_unit_id=journal["work_unit_id"],
                            calculation_revision_id=journal["calculation_revision_id"],
                            profile_label="Session02 Google Review",
                            output_dir=root / "logs/live-export-acceptance" / journal["run_id"] / "tui",
                            workspace_root=workspace,
                        )
                        return evidence.to_dict()

                print(json.dumps(asyncio.run(run_tui())), flush=True)
                return
            if mode in {"resume", "reconcile", "organize", "review"}:
                script = (
                    private / "review_google.py"
                    if mode == "review"
                    else private / "organize_google.py"
                    if mode == "organize"
                    else private / "resume_google.py"
                    if mode == "resume"
                    else root / "session02-driver/reconcile_operations.py"
                )
                runpy.run_path(str(script), run_name="__main__")
                return
            secret = win32crypt.CryptUnprotectData(
                (root / "session02-driver/synthetic-profile-input.dpapi").read_bytes(), None, None, None, 0
            )[1].decode()
            read_fd, write_fd = os.pipe()
            os.write(write_fd, json.dumps({"profile_passphrase": secret}).encode())
            os.close(write_fd)
            del secret
            handle = msvcrt.get_osfhandle(read_fd)
            os.set_handle_inheritable(handle, True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": [handle]}
            argv = [
                sys.executable,
                "-m",
                "cadrumo.entrypoints.cli._windows_profile_secret_bootstrap",
                "--profile-handle",
                str(handle),
                "--",
                "--format",
                "json",
                "--profile",
                "Session02 Google Review",
                *commands[mode],
            ]
            print(json.dumps({"stage": "cli", "action": mode}), flush=True)
            exit_code = 0
            with (
                (private / f"{mode}.json").open("w", encoding="utf-8") as out,
                (private / f"{mode}.stderr").open("w", encoding="utf-8") as err,
            ):
                try:
                    exit_code = subprocess.run(  # noqa: S603 -- fixed CLI bootstrap and explicit inherited secret handle.
                        argv,
                        stdout=out,
                        stderr=err,
                        startupinfo=startup,
                        close_fds=True,
                        check=False,
                        creationflags=0x08000000,
                    ).returncode
                finally:
                    with suppress(OSError):
                        os.close(read_fd)
            print(json.dumps({"stage": "settled", "exit_code": exit_code}), flush=True)
        finally:
            endpoint.close()
            if process.poll() is None:
                control = process.stdin
                if control is None:
                    raise RuntimeError("owned runtime lost its supervisor input")
                control.write(b'{"type":"stop"}\n')
                control.flush()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    win32job.TerminateJobObject(job, 1)
                    process.wait(timeout=10)
            job.Close()
            print(json.dumps({"stage": "runtime_stopped", "exit_code": process.returncode}), flush=True)


if __name__ == "__main__":
    main()
