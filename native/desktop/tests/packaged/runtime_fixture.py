"""Own a real packaged runtime for one interactive desktop acceptance run.

This script runs under the packaged interpreter and starts against a fresh root.
After its verified handshake the harness creates a profile through aeat and asks
this helper to bind that profile. No test login observer or development session
override is installed. EOF ends the contained runtime and its children.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import (
    delete_profile_session,
    profile_session_path,
)
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.paths import effective_storage_root
from cadrumo.domain.calculations.registry.authority import published_authority_generation
from cadrumo.entrypoints.adapter_composition import profile_free_adapter_composition


def emit(record: dict[str, str | int]) -> None:
    """Write only the fixture's bounded, credential-free control records."""
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def selected_profile_id() -> UUID | None:
    """Observe only the profile selected under this fixture's isolated root."""
    with profile_free_adapter_composition():
        bucket_id = observe_active_profile_pointer().bucket_id
    return UUID(bucket_id) if bucket_id is not None else None


def main() -> None:
    """Keep exact process ownership until the parent closes the control pipe."""
    if any(name.upper() == "CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE" for name in os.environ):
        raise RuntimeError("development session override is not acceptance")
    root = effective_storage_root().resolve(strict=True)
    profile_id: UUID | None = None
    try:
        runtime = Path(sys.argv[1]).resolve(strict=True)
        product = version("cadrumo")
        with ExitStack() as cleanup:
            endpoint = WindowsRuntimeEndpoint(storage_root=root)
            cleanup.callback(endpoint.close)
            scope = WindowsProcessScope()
            cleanup.callback(scope.terminate, timeout=10)
            runtime_installation(
                storage_root=root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
            )
            process = scope.launch(
                executable=runtime,
                directory=root,
                environment=dict(os.environ),
                arguments=(
                    "--storage-root",
                    str(root),
                    "--storage-identity",
                    endpoint.storage_identity,
                    "--expected-version",
                    product,
                ),
            )
            expected = RuntimeClientHello(
                product_version=product,
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            )
            deadline = time.monotonic() + 90
            while True:
                try:
                    channel = endpoint.connect(timeout=0.2, expected_image=runtime)
                    connection = VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline)
                    connection.close()
                    break
                except RuntimeRefusalError as error:
                    if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                        raise
                    try:
                        code = process.wait(timeout=0)
                    except RuntimeRefusalError as waiting:
                        if waiting.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                            raise
                        time.sleep(0.05)
                    else:
                        raise RuntimeError(f"runtime exited before handshake: {code}") from error
            emit(
                {
                    "kind": "ready",
                    "pid": process.pid,
                    "storageIdentity": endpoint.storage_identity,
                    "osOwnerId": endpoint.os_owner_id,
                }
            )
            while command := sys.stdin.buffer.readline(32):
                if command != b"profile-created\n" or profile_id is not None:
                    raise RuntimeError("invalid fixture control")
                profile_id = selected_profile_id()
                if profile_id is None:
                    raise RuntimeError("profile creation did not select a profile")
                emit({"kind": "profile-ready", "profileId": str(profile_id)})
            try:
                exit_code = process.wait(timeout=0)
            except RuntimeRefusalError as waiting:
                if waiting.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
                emit({"kind": "runtime-alive-before-cleanup", "pid": process.pid})
            else:
                emit({"kind": "runtime-exited-before-cleanup", "pid": process.pid, "exitCode": exit_code})
    finally:
        # Narrow fixture teardown, as in the secure-storage integration fixtures:
        # address only the new profile under this fresh root, after runtime exit.
        # Normal acceptance signs out through the canonical host command first.
        # A failed CLI response can leave a partially created profile before its
        # binding command arrives; resolve that exact isolated selection as well.
        if profile_id is None:
            profile_id = selected_profile_id()
        if profile_id is not None:
            delete_profile_session(storage_root=root, profile_id=profile_id)
            receipt_path = profile_session_path(storage_root=root, profile_id=profile_id)
            if receipt_path.exists() or receipt_path.is_symlink():
                raise RuntimeError("exact-profile receipt remained after fixture cleanup")
            emit({"kind": "profile-cleaned", "profileId": str(profile_id)})
        else:
            emit({"kind": "setup-incomplete", "detail": "no selected profile or sign-in receipt minted"})
    emit({"kind": "stopped"})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never emit an exception payload that could contain fixture secrets.
        emit({"kind": "failed", "errorType": type(error).__name__})
        raise SystemExit(1) from None
