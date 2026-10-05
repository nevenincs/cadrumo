"""Current-source CLI authentication against a real session-owned Windows runtime.

Run through ``just test-runtime-auth`` on the signed-in desktop. The normal
project environment supplies the entrypoints; pytest owns temporary storage.
No package, login observer override, fake keyring or generated host is used.
"""

from __future__ import annotations

import json
import secrets
import sys
import sysconfig
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ....adapters.local_runtime.framing import VerifiedRuntimeConnection
from ....adapters.local_runtime.installation import runtime_installation
from ....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from ....adapters.local_runtime.windows_desktop_logon import current_windows_desktop_logon
from ....adapters.local_runtime.windows_process import WindowsProcessScope
from ....adapters.persistence.storage.custody.acceleration_receipt import (
    delete_profile_session,
    profile_session_path,
)
from ....application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ....core.storage_environment import ChildEnvironmentProfile, child_environment
from ....domain.calculations.registry.authority import published_authority_generation
from ....tests.audited_process import run_audited_process

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only, pytest.mark.os_keychain]


class _Cli:
    def __init__(self, executable: Path, root: Path, environment: dict[str, str]) -> None:
        self.executable, self.root, self.environment = executable, root, environment

    def call(
        self, *arguments: str, secret: dict[str, str] | None = None, success: bool | None = True
    ) -> dict[str, Any]:
        payload = None if secret is None else bytearray(json.dumps(secret), "utf-8")
        try:
            completed = run_audited_process(
                [str(self.executable), "--format", "json", "config", *arguments],
                input=None if payload is None else bytes(payload),
                capture_output=True,
                env=self.environment,
                cwd=self.root,
                timeout=300 if arguments[:2] == ("profile", "create") else 30,
                check=False,
            )
        finally:
            if payload is not None:
                payload[:] = bytes(len(payload))
        document = json.loads(completed.stdout if completed.returncode == 0 else completed.stderr)
        assert document["schema_version"] == "2"
        if success is not None and (completed.returncode == 0) != success:
            error = document.get("error", {})
            values = (error.get("code"), error.get("context", {}).get("reason"))
            identifiers = [
                value
                for value in values
                if isinstance(value, str)
                and len(value) <= 80
                and value.isascii()
                and value.replace("_", "").isalnum()
                and value not in (secret or {}).values()
            ]
            pytest.fail(
                f"config {' '.join(arguments[:2])}: unexpected exit {completed.returncode}; {'/'.join(identifiers)}",
                pytrace=False,
            )
        return document


def test_native_runtime_password_login_shared_presence_and_logout(tmp_path: Path) -> None:
    """Wrong proof refuses; native custody persists, shares and revokes human access."""
    if sys.platform != "win32":
        pytest.fail("This native authentication test requires a Windows signed-in desktop", pytrace=False)
    try:
        current_windows_desktop_logon()
    except RuntimeRefusalError:
        pytest.fail(
            "Run just test-runtime-auth from the signed-in desktop; Session 0 is not authentication evidence",
            pytrace=False,
        )

    scripts = Path(sysconfig.get_path("scripts"))
    cli_path, runtime_path = scripts / "aeat.exe", scripts / "cadrumo-runtime.exe"
    assert cli_path.is_file() and runtime_path.is_file(), "Install the normal project development environment first"
    root = tmp_path / "storage"
    root.mkdir()
    environment = child_environment(ChildEnvironmentProfile.STRICT, root)
    environment["CADRUMO_CLI_REVEAL_IDENTIFIERS"] = "true"
    cli = _Cli(cli_path, root, environment)
    password = f"Native-auth-{secrets.token_urlsafe(24)}!"
    created = cli.call(
        "profile",
        "create",
        "Native authentication test",
        "--quiet",
        "--secrets-stdin",
        secret={"passphrase": password, "passphrase_confirmation": password},
    )
    assert created["status"] == "success"
    profile_id: UUID | None = None
    try:
        with ExitStack() as resources:
            endpoint = WindowsRuntimeEndpoint(storage_root=root)
            resources.callback(endpoint.close)
            scope = WindowsProcessScope()
            resources.callback(scope.terminate, timeout=10)
            runtime_installation(
                storage_root=root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
            )
            process = scope.launch(
                executable=runtime_path,
                arguments=(
                    "--storage-root",
                    str(root),
                    "--storage-identity",
                    endpoint.storage_identity,
                    "--expected-version",
                    version("cadrumo"),
                ),
                directory=root,
                environment=environment,
            )
            expected = RuntimeClientHello(
                product_version=version("cadrumo"),
                storage_identity=endpoint.storage_identity,
                authority_generation=published_authority_generation(),
            )
            deadline = time.monotonic() + 90
            while True:
                try:
                    channel = endpoint.connect(timeout=0.2)
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
                    else:
                        pytest.fail(f"Runtime exited before readiness: {code}", pytrace=False)
                    time.sleep(0.05)
            before = cli.call("sign-in-status")["result"]
            profile_id = UUID(before["profile_id"])
            assert before["status"]["presence"] == "absent"
            wrong = cli.call(
                "login",
                "--secrets-stdin",
                secret={"passphrase": f"Rejected-{secrets.token_urlsafe(24)}!"},
                success=False,
            )
            assert wrong["error"]["context"]["reason"] == "credential_rejected"
            assert cli.call("sign-in-status")["result"]["status"]["presence"] == "absent"
            # One explicit wrong proof can impose a runtime-owned delay. Read
            # that refusal rather than retrying a mutation after a transport error.
            admitted = cli.call("login", "--secrets-stdin", secret={"passphrase": password}, success=None)
            if admitted["status"] == "error":
                refusal = admitted["error"]["context"]
                assert refusal["reason"] == "authentication_required"
                assert refusal["sign_in_reason"] == "throttled"
                seconds = int(refusal["seconds"])
                assert 0 <= seconds <= 120
                time.sleep(seconds + 0.5)
                admitted = cli.call("login", "--secrets-stdin", secret={"passphrase": password})
            assert admitted["result"]["session_persisted"] is True
            present = cli.call("sign-in-status")["result"]
            assert present["profile_id"] == str(profile_id)
            assert present["status"]["presence"] == "present"
            revoked = cli.call("logout")["result"]
            assert revoked["human_receipt_revoked"] is True
            assert revoked["receipt_removed"] is True
            assert revoked["keychain_removed"] is True
            assert revoked["automation_revoked"] is False
            after = cli.call("sign-in-status")["result"]
            assert after["profile_id"] == str(profile_id)
            assert after["status"]["presence"] == "absent"
            assert not profile_session_path(storage_root=root, profile_id=profile_id).exists()
    finally:
        if profile_id is not None:
            delete_profile_session(storage_root=root, profile_id=profile_id)
