"""Installed MCP stdio reads one exact synthetic credential from native custody.

OS-login observations and the initial enrollment recipient are synthetic fixture
controls. The installed MCP process reads a reference from real client native
custody and completes its pinned result through the actual profile worker. Both
platforms use real native server control/wrap custody and inspect its exact
records and worker identity and live process. Linux additionally checks kernel
containment. This does not establish a real desktop login lifecycle.
"""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import (
    NativeClientCredentialStore,
)
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AUTH_READ_RESULT_SCHEMA_ID
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.tests.os_keychain_hook import require_os_credential_store

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux"}, reason="installed native admission is covered on Windows/Linux"
    ),
]

_AUTH_READ = AUTH_READ_OPERATION_DEFINITION_ID


def _scope_for_auth_read(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({_AUTH_READ}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=AUTH_READ_RESULT_SCHEMA_ID,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            }
        ),
        periods=frozenset[Period](),
        allow_period_independent=True,
        allow_delegation=False,
    )


def _unused_reference(store: NativeClientCredentialStore) -> UUID:
    """Choose a random exact reference after a canonical metadata-only read."""
    for _ in range(8):
        reference = uuid4()
        try:
            store.inspect(credential_reference=reference)
        except AutomationCustodyError as error:
            if error.reason is AutomationCustodyCode.MISSING:
                return reference
            if error.reason is AutomationCustodyCode.UNAVAILABLE:
                raise
        # A pre-existing or malformed exact account is left untouched. No
        # global native-store enumeration is performed.
    raise AssertionError("could not reserve an unused synthetic credential reference")


def _object(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _prepare_empty_profile(_profile_id: UUID, _root: Path) -> None:
    """The auth status read needs no private domain records."""


def _native_backend_for_current_platform() -> NativeSecretBackend:
    if sys.platform == "win32":
        return NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER
    if sys.platform == "linux":
        return NativeSecretBackend.LINUX_DBUS
    pytest.skip("installed native admission is covered on Windows/Linux")


def _installed_mcp_executable() -> Path:
    launcher = "cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp"
    return Path(sysconfig.get_path("scripts")) / launcher


@pytest.mark.anyio
async def test_installed_stdio_authenticates_and_reads_pinned_auth_result(tmp_path: Path) -> None:
    require_os_credential_store()
    backend = _native_backend_for_current_platform()
    native_store = native_automation_secret_store(backend)
    assert native_store.backend is backend
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_auth_read,
        prepare_profile=_prepare_empty_profile,
        server_native_store=native_store,
    ) as profile:
        # Initial delivery uses a synthetic client store. The new reference
        # goes to real client native custody; server control and unwrap
        # keys use that native provider too. Profile admission and execution
        # use the actual worker, with synthetic login observations.
        source = NativeClientCredentialStore.resolve_reference(
            credential_reference=profile.credential_reference,
            binding=profile.binding,
            secrets_store=profile._client_native,
        )
        source_metadata = source.metadata
        protected_store = NativeClientCredentialStore(
            secrets_store=native_store,
            binding=profile.binding,
            client_id=source_metadata.client_id,
            destination_id=source_metadata.destination_id,
        )
        reference = _unused_reference(protected_store)
        primary: BaseException | None = None

        try:
            published = protected_store.replace(
                credential_reference=reference,
                grant_id=source_metadata.grant_id,
                key_id=source_metadata.key_id,
                review_digest=source_metadata.review_digest,
                credential=source.read(),
            )
            readback = NativeClientCredentialStore.resolve_reference(
                credential_reference=reference,
                binding=profile.binding,
                secrets_store=native_store,
            )
            assert readback.metadata == published
            # The canonical handle verifies the exact native bytes and key id.
            assert readback.read()

            executable = _installed_mcp_executable()
            assert executable.is_file(), "the installed cadrumo-mcp executable is required"
            parameters = StdioServerParameters(
                command=str(executable),
                args=["--profile-id", str(profile.profile_id), "--credential-reference", str(reference)],
                cwd=tmp_path,
                env={
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                    "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                    "PYDANTIC_DISABLE_PLUGINS": "__all__",
                },
            )
            with (tmp_path / "installed-mcp.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()

                    status_call = await client.call_tool("status", {})
                    assert status_call.is_error is False
                    status_document = _object(status_call.structured_content)
                    assert status_document["outcome"] == "status"
                    status = _object(status_document["status"])
                    assert status["connected"] is True
                    assert status["credential_authenticated"] is True
                    assert status["profile_bound"] is True
                    assert status["profile_id"] == str(profile.profile_id)
                    assert status["denial"] is None

                    custody = profile.server_custody_health()
                    assert custody.binding == profile.binding
                    assert custody.backend is backend
                    assert custody.control_anchor_present is True
                    assert custody.grant_ids == (source_metadata.grant_id,)
                    assert custody.key_ids == (source_metadata.key_id,)
                    assert custody.wrap_count == 1
                    assert custody.wrapping_keys_valid is True
                    assert custody.runtime_uses_same_store is True
                    worker = profile.worker_health(UUID(cast("str", status["session_id"])))
                    assert worker.identity.binding == profile.binding
                    assert worker.identity.binding.profile_id == profile.profile_id
                    assert worker.alive is True
                    assert worker.worker_process_id > 0
                    assert worker.worker_process_id != worker.runtime_process_id
                    assert worker.admitted_session_count == 1
                    assert worker.exact_session_admitted is True
                    if sys.platform == "linux":
                        assert worker.linux_scope_owns_worker is True
                        assert worker.guardian_process_id is not None
                        assert worker.guardian_process_id > 0
                        assert worker.guardian_process_id not in {
                            worker.worker_process_id,
                            worker.runtime_process_id,
                        }
                        assert worker.control_group is not None
                        assert worker.control_group.endswith(f"/cadrumo-worker-{worker.identity.worker_id.hex}.service")
                        assert worker.kernel_control_groups_match is True

                    search_call = await client.call_tool("search", {"query": _AUTH_READ})
                    assert search_call.is_error is False
                    search_document = _object(search_call.structured_content)
                    assert search_document["outcome"] == "found"
                    operations = cast("list[dict[str, Any]]", search_document["operations"])
                    assert any(item["definition_id"] == _AUTH_READ for item in operations)

                    describe_call = await client.call_tool("describe", {"definition_id": _AUTH_READ})
                    assert describe_call.is_error is False
                    describe_document = _object(describe_call.structured_content)
                    assert describe_document["outcome"] == "described"
                    description = _object(describe_document["description"])
                    contract = _object(description["contract"])
                    assert contract["definition_id"] == _AUTH_READ
                    result_schema = _object(contract["result_schema"])
                    assert result_schema["schema_id"] == AUTH_READ_RESULT_SCHEMA_ID

                    execute_call = await client.call_tool(
                        "execute",
                        {
                            "definition_id": _AUTH_READ,
                            "subject_ref": f"profile:{profile.profile_id}",
                            "payload": {"profile_id": str(profile.profile_id), "kind": "status"},
                        },
                    )
                    assert execute_call.is_error is False
                    execution = _object(execute_call.structured_content)
                    assert execution["outcome"] == "submitted"
                    receipt = _object(execution["receipt"])
                    operation_id = cast(str, receipt["operation_id"])
                    start = _object(execution["start"])
                    assert start["operation_id"] == operation_id

                    observed_projection: dict[str, Any] | None = None
                    for _ in range(100):
                        observe_call = await client.call_tool(
                            "observe",
                            {
                                "observation": {
                                    "observation_version": 1,
                                    "operation_id": operation_id,
                                    "after_cursor": 0,
                                    "page_limit": 1000,
                                }
                            },
                        )
                        assert observe_call.is_error is False
                        observed_reply = _object(_object(observe_call.structured_content)["reply"])
                        assert observed_reply["kind"] == "operation_observed"
                        observation = _object(observed_reply["observation"])
                        assert observation["outcome"] == "success"
                        projection = _object(observation["projection"])
                        if projection["lifecycle"] == "terminal":
                            observed_projection = projection
                            break
                        await anyio.sleep(0.05)
                    assert observed_projection is not None, "registered auth read did not settle"
                    assert observed_projection["operation_id"] == operation_id
                    assert observed_projection["definition_id"] == _AUTH_READ
                    assert observed_projection["subject_ref"] == f"profile:{profile.profile_id}"
                    assert observed_projection["terminal_condition"] == "succeeded"
                    assert observed_projection["effect"] == "none"
                    assert observed_projection["definition_contract"] == contract

                    result_call = await client.call_tool(
                        "result",
                        {
                            "result": {
                                "result_projection_version": 1,
                                "operation_id": operation_id,
                                "terminal_revision": observed_projection["revision"],
                                "definition_contract_digest": contract["definition_contract_digest"],
                                "result_schema": result_schema,
                            }
                        },
                    )
                    assert result_call.is_error is False
                    result_document = _object(_object(result_call.structured_content)["document"])
                    assert result_document["outcome"] == "success"
                    assert result_document["definition_contract_digest"] == contract["definition_contract_digest"]
                    assert result_document["result_schema"] == result_schema
                    auth_projection = _object(result_document["projection"])
                    assert auth_projection["profile_id"] == str(profile.profile_id)
                    assert auth_projection["kind"] == "status"
                    assert auth_projection["status"] is not None

                    wrong_reference = uuid4()
                    denied = await client.call_tool("authenticate", {"credential_reference": str(wrong_reference)})
                    assert denied.is_error is True
                    assert denied.structured_content == {"outcome": "refused", "code": "missing"}
                    after_denial_call = await client.call_tool("status", {})
                    assert after_denial_call.is_error is False
                    after_denial = _object(_object(after_denial_call.structured_content)["status"])
                    assert after_denial["session_id"] == status["session_id"]
                    assert after_denial["profile_id"] == str(profile.profile_id)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                protected_store.delete(
                    credential_reference=reference,
                    grant_id=source_metadata.grant_id,
                    key_id=source_metadata.key_id,
                    review_digest=source_metadata.review_digest,
                )
            except BaseException as cleanup_error:
                if primary is None:
                    raise
                primary.add_note(
                    f"exact synthetic native credential cleanup also failed ({type(cleanup_error).__name__})"
                )
