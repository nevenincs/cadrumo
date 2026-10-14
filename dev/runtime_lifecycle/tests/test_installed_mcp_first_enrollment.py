"""The installed SDK offers an agent no way to request, approve or present a key of its own.

A key is issued by the person with ``config automation`` and given to the MCP
server by reference in its launch configuration. An unauthenticated installed
server therefore answers its tool list and ``status``, refuses the profile's
operations, and has no tool that prepares, submits, polls or presents an
enrollment. The encrypted profile, runtime, workers and native secret store are
real. Linux acceptance requires the selected protected GNOME fixture; Windows
acceptance requires the selected normal-desktop Windows Credential Manager
fixture. OS-login observations are synthetic setup.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import Result
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.storage.custody.automation_secret_store import (
    WindowsAutomationSecretStore,
    native_automation_secret_store,
)
from cadrumo.adapters.persistence.storage.custody.linux_secret_service_store import (
    LinuxSecretServiceAutomationSecretStore,
)
from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AuthReadRequest
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore, NativeSecretBackend
from cadrumo.core.config import override_settings
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo_runtime.host.tests.frontend.cli.native_api_cli_support import native_api_cli_session

from .records import _record
from .test_installed_authenticated_stdio import _installed_mcp_executable, _scope_for_auth_read

if TYPE_CHECKING:
    pass

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"linux", "win32"},
        reason="requires installed MCP and a supported native secret store",
    ),
]

_GNOME_EXPECTATION = "CADRUMO_TEST_GNOME_COLLECTION_EXPECTATION"
_WINDOWS_EXPECTATION = "CADRUMO_TEST_WINDOWS_CREDENTIAL_MANAGER_EXPECTATION"


def _selected_native_store() -> tuple[NativeSecretBackend, AutomationSecretStore]:
    """Use only the explicitly selected protected store for this machine."""
    if os.environ.get(_GNOME_EXPECTATION) == "protected" and sys.platform != "linux":
        pytest.fail("protected GNOME acceptance requires Linux", pytrace=False)
    if os.environ.get(_WINDOWS_EXPECTATION) == "protected" and sys.platform != "win32":
        pytest.fail("protected Windows Credential Manager acceptance requires Windows", pytrace=False)

    if sys.platform == "linux":
        selected = os.environ.get(_GNOME_EXPECTATION)
        if selected is None:
            pytest.skip("requires explicit protected GNOME native custody selection")
        if selected == "unsuitable":
            pytest.skip("the selected GNOME collection is unsuitable for protected delivery")
        if selected != "protected":
            pytest.fail("GNOME collection expectation must be protected or unsuitable", pytrace=False)
        backend = NativeSecretBackend.LINUX_DBUS
        store = native_automation_secret_store(backend)
        assert isinstance(store, LinuxSecretServiceAutomationSecretStore)
        return backend, store

    if sys.platform == "win32":
        require_selected_normal_desktop()
        backend = NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER
        store = native_automation_secret_store(backend)
        assert isinstance(store, WindowsAutomationSecretStore)
        return backend, store

    pytest.skip("requires Linux Secret Service or Windows Credential Manager")


_KEY_REQUEST_CALLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("authorization_prepare", {}),
    ("authorization_request", {"proposal": {}}),
    ("authorization_poll", {}),
    ("authenticate", {"credential_reference": "00000000-0000-4000-8000-000000000000"}),
)


@pytest.mark.anyio
async def test_installed_sdk_offers_no_enrollment_and_no_key_presentation_to_an_agent(
    tmp_path: Path, run_cadrumo_cli: Callable[..., Result]
) -> None:
    """An unauthenticated SDK can neither request a key for itself nor name one; the person issues and configures it."""
    _backend, native_store = _selected_native_store()
    executable = _installed_mcp_executable()
    assert executable.is_file(), "the installed cadrumo-mcp executable is required"
    with (
        override_settings(
            cadrumo_output_language="en",
            cadrumo_profile_kdf_measure_calibration=False,
            cadrumo_cli_reveal_identifiers=True,
        ),
        native_api_cli_session(
            tmp_path,
            invoke_cli=run_cadrumo_cli,
            scope_for_destination=_scope_for_auth_read,
            prepare_profile=lambda _profile_id, _root: None,
            server_native_store=native_store,
        ) as profile,
    ):
        parameters = StdioServerParameters(
            command=str(executable),
            args=["--profile-id", str(profile.profile_id)],
            cwd=tmp_path,
            env={
                "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                "PYDANTIC_DISABLE_PLUGINS": "__all__",
            },
        )
        sessions_before = profile.registered_sessions()
        with (tmp_path / "first-enrollment.stderr").open("w", encoding="utf-8") as error_log:
            async with (
                stdio_client(parameters, errlog=error_log) as (reader, writer),
                ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
            ):
                await sdk.initialize()
                names = {tool.name for tool in (await sdk.list_tools()).tools}
                status = await sdk.call_tool("status", {})
                private_arguments = {
                    "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                    "subject_ref": profile_operation_subject(str(profile.profile_id)),
                    "payload": AuthReadRequest(profile_id=profile.profile_id, kind="status").model_dump(mode="json"),
                }
                refused = await sdk.call_tool("execute", private_arguments)
                key_requests = [await sdk.call_tool(name, arguments) for name, arguments in _KEY_REQUEST_CALLS]

        assert not names & {name for name, _arguments in _KEY_REQUEST_CALLS}
        assert not status.is_error
        assert _record(status.structured_content)["authenticated"] is False
        assert refused.is_error
        assert _record(refused.structured_content)["code"] == "authentication_required"
        for (name, _arguments), answer in zip(_KEY_REQUEST_CALLS, key_requests, strict=True):
            assert answer.is_error, name
            assert _record(answer.structured_content) == {"outcome": "refused", "code": "unknown_tool"}, name
        # Nothing the server was asked admitted a session for it.
        assert profile.registered_sessions() == sessions_before
