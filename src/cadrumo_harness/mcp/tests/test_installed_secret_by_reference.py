"""A started `cadrumo-mcp` process takes a secret by reference from this machine's credential store.

Nothing here stands in for a component. The server is the installed console
script in a process of its own, the runtime is the installed runtime in
another, the profile is a real encrypted profile created with a real password
through the production registration, and the held secret is put in the
platform's credential store by the same custody call `cadrumo-mcp
--hold-secret` makes. The storage root, the processes and every held secret
are created and removed by the test.

The first case gives the same secrets as text. It needs no credential store,
so it runs wherever the installed entry points do, and it holds the rest of
the journey to the real processes. The by-reference cases need a credential
store this logon session can use and carry the ``os_keychain`` marker.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import sysconfig
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.tests.os_keychain_hook import require_os_credential_store
from cadrumo_harness.mcp.held_secrets import HeldSecretCustody, installed_held_secret_custody

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires installed Windows MCP and runtime launchers"),
]

_PROFILE_INPUT = "synthetic-profile-password-6c1e"
_EXPORT_TEXT = "synthetic-export-passphrase-93bd"
_SECRETS = (_PROFILE_INPUT, _EXPORT_TEXT)
_INVALID = {"outcome": "refused", "code": "invalid_request"}


@dataclass(frozen=True, slots=True)
class _Served:
    """One real profile served by one installed runtime, and the installed server to reach it with."""

    storage_root: Path
    profile_id: UUID
    mcp_executable: Path


@contextmanager
def _installed_runtime_over_a_real_profile(tmp_path: Path) -> Iterator[_Served]:
    scripts = Path(sysconfig.get_path("scripts"))
    mcp_executable, runtime_executable = scripts / "cadrumo-mcp.exe", scripts / "cadrumo-runtime.exe"
    assert mcp_executable.is_file() and runtime_executable.is_file(), "install the development entry points first"

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root, ExitStack() as cleanup:
        storage_root.mkdir(parents=True, exist_ok=True)
        endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
        cleanup.callback(endpoint.close)
        scope = WindowsProcessScope()
        cleanup.callback(scope.terminate, timeout=5)
        runtime_installation(
            storage_root=storage_root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
        )
        # The record is created under the published authority the installed runtime reads it back with.
        with composed_profile_persistence_ports(), bundled_indexed_authority().operation():
            create, decode = profile_authority_contexts()
            registered = register_profile_with_credentials(
                label="Installed MCP secret by reference",
                passphrase=_PROFILE_INPUT,
                profile_create_context=create,
                profile_decode_context=decode,
            )
            # Registration leaves the profile unlocked in this process; the runtime is what serves it.
            close_active_bucket_session()

        runtime_environment = {
            name: value for name, value in os.environ.items() if not name.upper().startswith(("PYTHON", "LD_", "DYLD_"))
        }
        runtime_environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(storage_root)
        scope.launch(
            executable=runtime_executable.resolve(strict=True),
            arguments=(
                "--storage-root",
                str(storage_root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                version("cadrumo"),
            ),
            directory=storage_root,
            environment=runtime_environment,
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                VerifiedRuntimeConnection(
                    endpoint.connect(timeout=0.2),
                    expected=RuntimeClientHello(
                        product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                    ),
                    deadline=deadline,
                ).close()
                break
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)
        yield _Served(storage_root, UUID(registered.profile_id), mcp_executable)


async def _settled(client: ClientSession, submitted: dict[str, Any]) -> dict[str, Any]:
    """Observe a submitted operation until the runtime reports it terminal, and return that projection."""
    assert submitted["outcome"] == "submitted", submitted
    request = {
        "observation_version": 1,
        "operation_id": submitted["receipt"]["operation_id"],
        "after_cursor": 0,
        "page_limit": 1,
    }
    for _attempt in range(300):
        observed = await client.call_tool("observe", {"observation": request})
        assert isinstance(observed.structured_content, dict), observed
        if observed.structured_content == {"outcome": "refused", "code": RuntimeRefusalCode.DEADLINE_EXCEEDED.value}:
            # The runtime was busy with the operation for longer than one read waits; a read is asked again.
            continue
        assert observed.is_error is False, observed
        projection = observed.structured_content["reply"]["observation"]["projection"]
        if projection["lifecycle"] == "terminal":
            return projection
        await asyncio.sleep(0.2)
    raise AssertionError("the operation did not settle")


async def _journey(
    served: _Served,
    stderr_path: Path,
    *,
    password: dict[str, str],
    export: dict[str, str],
    unknown_reference: bool,
) -> Any:
    """Sign in, settle one read, and export a bundle whose passphrase the operation declares as a secret.

    ``password`` and ``export`` are the tool arguments that carry each secret,
    as text or by reference, so both forms take the same journey. With
    ``unknown_reference`` the server is also asked to sign in with a reference
    that names nothing, which makes it read the credential store.
    """
    environment = child_environment(ChildEnvironmentProfile.STRICT, served.storage_root)
    environment["PYTHONIOENCODING"] = "utf-8"
    server = StdioServerParameters(
        command=str(served.mcp_executable.resolve(strict=True)),
        args=["--profile-id", str(served.profile_id)],
        env=environment,
        cwd=served.storage_root,
    )
    destination = served.storage_root / "exported" / "synthetic.bundle"
    destination.parent.mkdir()
    replies: dict[str, Any] = {}
    async with asyncio.timeout(300):
        with stderr_path.open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(server, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=120) as client,
            ):
                await client.initialize()
                replies["before"] = (await client.call_tool("status", {})).structured_content
                signed_in = await client.call_tool("session", {"action": "sign_in", **password})
                replies["signed_in"] = signed_in.structured_content
                assert signed_in.is_error is False, signed_in.structured_content
                read = await client.call_tool(
                    "execute",
                    {
                        "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                        "payload": {"profile_id": str(served.profile_id), "kind": "status"},
                    },
                )
                replies["read"] = read.structured_content
                # The same read without the field its request requires: the runtime's own refusal, explained.
                unfit = await client.call_tool(
                    "execute", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID, "payload": {"kind": "status"}}
                )
                replies["unfit_read"] = (unfit.is_error, unfit.structured_content)
                replies["read_settled"] = await _settled(client, replies["read"])
                exported = await client.call_tool(
                    "execute",
                    {
                        "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                        "payload": {
                            "profile_id": str(served.profile_id),
                            "destination": str(destination),
                            "purpose": "portable_transfer",
                        },
                        **export,
                    },
                )
                replies["exported"] = exported.structured_content
                replies["export_settled"] = await _settled(client, replies["exported"])
                if unknown_reference:
                    nothing_held = {"action": "sign_in", "secret_reference": str(uuid4())}
                    unknown = await client.call_tool("session", nothing_held)
                    replies["unknown_reference"] = (unknown.is_error, unknown.structured_content)
    replies["bundle_written"] = destination.is_file()
    return replies


def _assert_a_live_session_ran_both_operations(replies: dict[str, Any], served: _Served) -> None:
    assert replies["before"]["session"] == "none"
    assert replies["signed_in"]["outcome"] == "signed_in" and replies["signed_in"]["session"] == "typed_sign_in"
    assert replies["signed_in"]["status"]["profile_id"] == str(served.profile_id)
    assert replies["read_settled"]["terminal_condition"] == "succeeded", replies["read_settled"]
    unfit_is_error, unfit = replies["unfit_read"]
    assert unfit_is_error is True and (unfit["outcome"], unfit["code"]) == ("refused", "invalid")
    assert unfit["faults"] == [{"location": ["profile_id"], "type": "missing", "message": "this field is required"}]
    assert replies["exported"]["secret_delivery"] == {"outcome": "delivered"}
    assert replies["export_settled"]["terminal_condition"] == "succeeded", replies["export_settled"]
    assert replies["bundle_written"] is True


def _assert_no_secret_left_the_protected_frame(replies: dict[str, Any], served: _Served, stderr_path: Path) -> None:
    """No tool result, no line the server wrote and no file under the storage root repeats a secret."""
    rendered = json.dumps(replies, default=str)
    for secret in _SECRETS:
        assert secret not in rendered
        assert secret not in stderr_path.read_text(encoding="utf-8")
        encoded = secret.encode("utf-8")
        for path in served.storage_root.rglob("*"):
            if path.is_file():
                assert encoded not in path.read_bytes(), path.name


def test_the_installed_processes_take_typed_secrets_through_sign_in_a_read_and_an_export(tmp_path: Path) -> None:
    stderr_path = tmp_path / "server.stderr"
    with _installed_runtime_over_a_real_profile(tmp_path) as served:
        replies = asyncio.run(
            _journey(
                served,
                stderr_path,
                password={"secret": _PROFILE_INPUT},
                export={"secret": _EXPORT_TEXT},
                unknown_reference=False,
            )
        )

        _assert_a_live_session_ran_both_operations(replies, served)
        _assert_no_secret_left_the_protected_frame(replies, served, stderr_path)


def _released(custody: HeldSecretCustody, references: list[UUID]) -> None:
    """Take out of the real store whatever a case put there and did not spend."""
    for reference in references:
        with suppress(AutomationCustodyError):
            custody.release(reference)


@pytest.mark.os_keychain
def test_the_installed_processes_take_the_same_secrets_by_reference_from_the_real_credential_store(
    tmp_path: Path,
) -> None:
    require_os_credential_store()
    stderr_path = tmp_path / "server.stderr"
    with _installed_runtime_over_a_real_profile(tmp_path) as served:
        custody = installed_held_secret_custody()
        held: list[UUID] = []
        try:
            profile_input, export_text = bytearray(_PROFILE_INPUT, "utf-8"), bytearray(_EXPORT_TEXT, "utf-8")
            kept = custody.hold_entered(label="synthetic kept", secret=profile_input, single_use=False)
            held.append(kept.reference)
            once = custody.hold_entered(label="synthetic once", secret=export_text, single_use=True)
            held.append(once.reference)

            replies = asyncio.run(
                _journey(
                    served,
                    stderr_path,
                    password={"secret_reference": str(kept.reference)},
                    export={"secret_reference": str(once.reference)},
                    unknown_reference=True,
                )
            )

            _assert_a_live_session_ran_both_operations(replies, served)
            # A reference that names nothing held is a mistaken argument, and the session
            # the kept reference admitted is untouched by it.
            assert replies["unknown_reference"] == (True, _INVALID)
            _assert_no_secret_left_the_protected_frame(replies, served, stderr_path)
            # The kept secret is still the person's to delete; the one held for one use is gone.
            assert custody.read(kept.reference).secret.get_secret_value() == _PROFILE_INPUT.encode()
            with pytest.raises(AutomationCustodyError) as spent:
                custody.read(once.reference)
            assert spent.value.reason is AutomationCustodyCode.MISSING
            assert [entry.reference for entry in custody.entries()] == [kept.reference]
        finally:
            _released(custody, held)
        assert custody.entries() == ()


async def _enable_recovery(served: _Served, stderr_path: Path, *, password_reference: UUID) -> dict[str, Any]:
    environment = child_environment(ChildEnvironmentProfile.STRICT, served.storage_root)
    environment["PYTHONIOENCODING"] = "utf-8"
    server = StdioServerParameters(
        command=str(served.mcp_executable.resolve(strict=True)),
        args=["--profile-id", str(served.profile_id)],
        env=environment,
        cwd=served.storage_root,
    )
    async with asyncio.timeout(300):
        with stderr_path.open("w", encoding="utf-8") as stderr:
            async with (
                stdio_client(server, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream, read_timeout_seconds=120) as client,
            ):
                await client.initialize()
                enabled = await client.call_tool(
                    "session", {"action": "enable_recovery", "secret_reference": str(password_reference)}
                )
    assert enabled.is_error is False and isinstance(enabled.structured_content, dict), enabled
    return enabled.structured_content


@pytest.mark.os_keychain
def test_a_recovery_code_enabled_by_reference_is_held_in_the_real_credential_store_and_in_no_reply(
    tmp_path: Path,
) -> None:
    require_os_credential_store()
    stderr_path = tmp_path / "server.stderr"
    with _installed_runtime_over_a_real_profile(tmp_path) as served:
        custody = installed_held_secret_custody()
        held: list[UUID] = []
        try:
            password = custody.hold_entered(
                label="synthetic kept", secret=bytearray(_PROFILE_INPUT, "utf-8"), single_use=True
            )
            held.append(password.reference)

            enabled = asyncio.run(_enable_recovery(served, stderr_path, password_reference=password.reference))

            assert enabled["outcome"] == "completed", enabled
            delivered = UUID(enabled["secret_reference"])
            held.append(delivered)
            assert f"cadrumo-mcp --show-held-secret {delivered}" in enabled["secret_retrieval"]
            code = custody.read(delivered)
            assert not code.entered and code.secret.get_secret_value()
            recovery_code = code.secret.get_secret_value().decode("utf-8")
            # The code is the person's to read: it is in no reply and no line the server wrote.
            assert recovery_code not in json.dumps(enabled) and _PROFILE_INPUT not in json.dumps(enabled)
            assert recovery_code not in stderr_path.read_text(encoding="utf-8")
            # A call may use it by its reference, which neither shows it nor counts as the person reading it.
            assert bytes(custody.take(delivered)) == recovery_code.encode("utf-8")
            assert [(entry.reference, entry.entered) for entry in custody.entries()] == [(delivered, False)]
        finally:
            _released(custody, held)
        assert custody.entries() == ()
