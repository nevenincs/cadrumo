"""Installed MCP reconnects one protected grant without retaining the prior session.

The enrolled recipient and OS-login observation are synthetic fixture controls.
Each MCP process reads its reference from the real platform native store. Server
control/wrap custody uses the same native provider and admission uses the real
runtime worker. This does not prove a desktop login lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import (
    ClientCredentialMetadata,
    NativeClientCredentialStore,
)
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, ProfileAccessStatus
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.entrypoints.cli.tests import native_api_cli_support
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.tests.os_keychain_hook import require_os_credential_store

from .test_installed_authenticated_stdio import (
    _installed_mcp_executable,
    _native_backend_for_current_platform,
    _scope_for_auth_read,
    _unused_reference,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux"}, reason="installed native admission is covered on Windows/Linux"
    ),
]

_LIVE_RETIREMENT_CODES = frozenset({"session_inactive", "connection_mismatch", "key_inactive", "grant_inactive"})
_REVOKED_KEY_CODES = frozenset({"key_inactive", "grant_inactive"})


def _object(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast("dict[str, Any]", value)


def _status(value: object, *, profile_id: UUID) -> ProfileAccessStatus:
    document = _object(value)
    assert document["outcome"] == "status"
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(document["status"]))
    assert status.profile_id == profile_id
    return status


@pytest.mark.anyio
async def test_installed_mcp_reconnects_same_native_grant_with_distinct_session_and_revocation_fence(
    tmp_path: Path,
) -> None:
    """Closing one stdio adapter retires only its session; revocation fences the next."""
    require_os_credential_store()
    backend = _native_backend_for_current_platform()
    native_store = native_automation_secret_store(backend)
    assert native_store.backend is backend
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_auth_read,
        prepare_profile=lambda _profile_id, _root: None,
        server_native_store=native_store,
    ) as profile:
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
            assert readback.metadata == published and readback.read()

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

            with (tmp_path / "installed-reconnect-first.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    first_call = await client.call_tool("status", {})
                    assert first_call.is_error is False
                    first = _status(first_call.structured_content, profile_id=profile.profile_id)
                    assert first.connected and first.credential_authenticated and first.profile_bound
                    assert first.denial is None and first.grant_valid
                    assert first.session_id is not None and first.session_expires_at is not None
                    assert first.session_expires_at > now()
                    assert first.grant_expires_at is not None and first.grant_expires_at > now()
                    assert profile.registered_sessions() == (first.session_id,)
                    custody = profile.server_custody_health()
                    assert custody.binding == profile.binding
                    assert custody.backend is backend
                    assert custody.control_anchor_present is True
                    assert custody.grant_ids == (source_metadata.grant_id,)
                    assert custody.key_ids == (source_metadata.key_id,)
                    assert custody.wrap_count == 1
                    assert custody.wrapping_keys_valid is True
                    assert custody.runtime_uses_same_store is True
                    first_worker = profile.worker_health(first.session_id)
                    assert first_worker.identity.binding == profile.binding
                    assert first_worker.identity.binding.profile_id == profile.profile_id
                    assert first_worker.alive and first_worker.exact_session_admitted
                    assert first_worker.worker_process_id > 0
                    assert first_worker.worker_process_id != first_worker.runtime_process_id
                    assert first_worker.admitted_session_count == 1

            # No worker lifetime is assumed while no adapter is connected.
            # The runtime remains ready and its old connection registration is gone.
            assert profile.registered_sessions() == ()
            runtime = profile.runtime_health()
            assert runtime.ready and not runtime.stop_requested and not runtime.serve_task_done

            with (tmp_path / "installed-reconnect-second.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    second_call = await client.call_tool("status", {})
                    assert second_call.is_error is False
                    second = _status(second_call.structured_content, profile_id=profile.profile_id)
                    assert second.connected and second.credential_authenticated and second.profile_bound
                    assert second.denial is None and second.grant_valid
                    assert second.session_id is not None and second.session_id != first.session_id
                    assert second.session_expires_at is not None and second.session_expires_at > now()
                    assert second.grant_expires_at == first.grant_expires_at
                    assert second.effective_scope == first.effective_scope
                    assert profile.registered_sessions() == (second.session_id,)
                    second_worker = profile.worker_health(second.session_id)
                    assert second_worker.identity.binding == profile.binding
                    assert second_worker.identity.binding.profile_id == profile.profile_id
                    assert second_worker.alive and second_worker.exact_session_admitted
                    assert second_worker.worker_process_id > 0
                    assert second_worker.worker_process_id != second_worker.runtime_process_id
                    assert second_worker.admitted_session_count == 1
                    assert not profile.worker_health(first.session_id).exact_session_admitted

                    private = await client.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert private.is_error is False
                    found = _object(private.structured_content)
                    assert found["outcome"] == "found"
                    assert any(
                        _object(item)["definition_id"] == AUTH_READ_OPERATION_DEFINITION_ID
                        for item in cast("list[object]", found["operations"])
                    )

                    described = await client.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert described.is_error is False
                    description = _object(_object(described.structured_content)["description"])
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(description["contract"])
                    )
                    assert contract.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
                    assert contract.result_schema is not None
                    request = AuthReadRequest(profile_id=profile.profile_id, kind="status")
                    submitted = await client.call_tool(
                        "execute",
                        {
                            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                            "subject_ref": profile_operation_subject(str(profile.profile_id)),
                            "payload": request.model_dump(mode="json"),
                        },
                    )
                    assert submitted.is_error is False
                    submission = _object(submitted.structured_content)
                    assert submission["outcome"] == "submitted"
                    receipt = OperationSubmissionReceiptV1.model_validate_json(
                        canonical_json_bytes(submission["receipt"])
                    )
                    observation = OperationObservationRequestV1(
                        operation_id=receipt.operation_id, after_cursor=0, page_limit=32
                    )
                    terminal: OperationObservationSuccessV1 | None = None
                    for _attempt in range(80):
                        observed = await client.call_tool(
                            "observe", {"observation": observation.model_dump(mode="json")}
                        )
                        assert observed.is_error is False
                        reply = _object(_object(observed.structured_content)["reply"])
                        candidate = OperationObservationSuccessV1.model_validate_json(
                            canonical_json_bytes(reply["observation"])
                        )
                        if candidate.projection.lifecycle is OperationLifecycle.TERMINAL:
                            terminal = candidate
                            break
                        await asyncio.sleep(0.05)
                    assert terminal is not None
                    assert terminal.projection.operation_id == receipt.operation_id
                    assert terminal.projection.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
                    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert terminal.projection.effect is OperationEffect.NONE
                    result_request = OperationResultProjectionRequestV1(
                        operation_id=receipt.operation_id,
                        terminal_revision=terminal.projection.revision,
                        definition_contract_digest=contract.definition_contract_digest,
                        result_schema=contract.result_schema,
                    )
                    result_args = {"result": result_request.model_dump(mode="json")}
                    released = await client.call_tool("result", result_args)
                    assert released.is_error is False
                    document = _object(_object(released.structured_content)["document"])
                    result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
                        canonical_json_bytes(document)
                    )
                    assert result.definition_contract_digest == contract.definition_contract_digest
                    assert result.result_schema == contract.result_schema
                    assert result.projection.profile_id == profile.profile_id
                    assert result.projection.kind == "status" and result.projection.status is not None

                    # This is an explicit human denial after the passwordless
                    # reconnect, through the established CLI authority owner.
                    delete_profile_session(storage_root=tmp_path / "cadrumo-storage", profile_id=profile.profile_id)
                    denied_output = await asyncio.to_thread(
                        profile.invoke_password,
                        "config",
                        "profile",
                        "automation",
                        "deny",
                        "key",
                        str(source_metadata.key_id),
                    )
                    assert denied_output.exit_code == 0, denied_output.output
                    denied_document = _object(json.loads(denied_output.stdout))
                    assert denied_document["command"] == "config.profile.automation.deny"
                    assert denied_document["status"] in {"success", "warning"}
                    denied_result = _object(denied_document["result"])
                    assert denied_result["kind"] == "key"
                    assert denied_result["target_id"] == str(source_metadata.key_id)
                    assert _object(denied_result["receipt"])["access_denied"] is True

                    inventory_output = await asyncio.to_thread(
                        profile.invoke_password, "config", "profile", "automation", "list"
                    )
                    assert inventory_output.exit_code == 0, inventory_output.output
                    inventory_document = _object(json.loads(inventory_output.stdout))
                    assert inventory_document["command"] == "config.profile.automation.list"
                    keys = cast("list[object]", _object(_object(inventory_document["result"])["inventory"])["keys"])
                    selected = [
                        _object(item) for item in keys if _object(item)["key_id"] == str(source_metadata.key_id)
                    ]
                    assert len(selected) == 1 and selected[0]["state"] == "revoked"

                    fenced = await client.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert fenced.is_error is True
                    refusal = _object(fenced.structured_content)
                    assert refusal["outcome"] == "refused" and refusal["code"] in _LIVE_RETIREMENT_CODES
                    cached_result = await client.call_tool("result", result_args)
                    assert cached_result.is_error is True
                    cached_refusal = _object(cached_result.structured_content)
                    assert cached_refusal["outcome"] == "refused"
                    assert cached_refusal["code"] in _LIVE_RETIREMENT_CODES
                    assert str(reference) not in repr(refusal)
                    assert str(reference) not in repr(cached_refusal)

            with (tmp_path / "installed-reconnect-revoked.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as client,
                ):
                    await client.initialize()
                    revoked_call = await client.call_tool("status", {})
                    assert revoked_call.is_error is False
                    revoked = _object(revoked_call.structured_content)
                    assert revoked["outcome"] == "status"
                    assert revoked["profile_id"] == str(profile.profile_id)
                    assert revoked["authenticated"] is False
                    assert revoked["denial"] in _REVOKED_KEY_CODES
                    denied_search = await client.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert denied_search.is_error is True
                    assert _object(denied_search.structured_content) == {
                        "outcome": "refused",
                        "code": revoked["denial"],
                    }
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


class _NativeReferenceCleanup:
    """Retain exactly the synthetic published client item until deletion succeeds."""

    def __init__(self, store: NativeClientCredentialStore, reference: UUID, metadata: ClientCredentialMetadata) -> None:
        self.store, self.reference, self.metadata = store, reference, metadata
        self.released = False

    def _delete(self) -> None:
        self.store.delete(
            credential_reference=self.reference,
            grant_id=self.metadata.grant_id,
            key_id=self.metadata.key_id,
            review_digest=self.metadata.review_digest,
        )
        self.released = True

    async def close(self) -> None:
        if not self.released:
            await await_cancellation_complete(
                asyncio.to_thread(self._delete), task_name="native-expiry-reference-delete"
            )


@pytest.mark.anyio
async def test_installed_mcp_independent_grant_executes_after_genuine_human_idle_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual UTC expiry retires human authority without suspending independent native custody."""
    require_os_credential_store()
    worker_script = tmp_path / "one-minute-idle-worker.py"
    worker_script.write_text(
        "from cadrumo.core.config import override_settings\n"
        "from cadrumo.entrypoints.runtime.worker import run\n"
        "with override_settings(cadrumo_bucket_default_idle_lock_minutes=1):\n"
        "    raise SystemExit(run())\n",
        encoding="utf-8",
    )
    # Only the fixture composition selects the trusted script; the real constructor and worker remain intact.
    monkeypatch.setattr(
        native_api_cli_support,
        "RuntimeProfileConnections",
        partial(RuntimeProfileConnections, worker_script=worker_script.resolve(strict=True)),
    )
    backend = _native_backend_for_current_platform()
    native_store = native_automation_secret_store(backend)
    assert native_store.backend is backend
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_auth_read,
        prepare_profile=lambda _profile_id, _root: None,
        server_native_store=native_store,
    ) as profile:
        source = await asyncio.to_thread(
            NativeClientCredentialStore.resolve_reference,
            credential_reference=profile.credential_reference,
            binding=profile.binding,
            secrets_store=profile._client_native,
        )
        metadata = source.metadata
        protected = NativeClientCredentialStore(
            secrets_store=native_store,
            binding=profile.binding,
            client_id=metadata.client_id,
            destination_id=metadata.destination_id,
        )
        reference = await asyncio.to_thread(_unused_reference, protected)
        reference_owner = _NativeReferenceCleanup(protected, reference, metadata)
        primary: BaseException | None = None
        try:
            credential = await asyncio.to_thread(source.read)
            try:
                await await_cancellation_complete(
                    asyncio.to_thread(
                        protected.replace,
                        credential_reference=reference,
                        grant_id=metadata.grant_id,
                        key_id=metadata.key_id,
                        review_digest=metadata.review_digest,
                        credential=credential,
                    ),
                    task_name="native-expiry-reference-publish",
                )
            finally:
                del credential
            human = await open_installed_runtime_client(
                profile_id=profile.profile_id, frontend=OperationFrontendProjection.CLI
            )
            human_primary: BaseException | None = None
            try:
                proof = bytearray(PROFILE_INPUT, "utf-8")
                try:
                    admitted = await await_cancellation_complete(
                        asyncio.to_thread(human.login_password, proof), task_name="native-expiry-human-login"
                    )
                    assert not any(proof)
                finally:
                    proof[:] = bytes(len(proof))
                human_status = admitted.status
                assert human_status.credential_authenticated and human_status.profile_bound
                assert human_status.profile_id == profile.profile_id and human_status.session_id == human.session_id
                human_session = human.session_id
                expiry = human_status.session_expires_at
                assert expiry is not None and timedelta(0) < expiry - now() <= timedelta(minutes=1)
                store = AutomationControlStore(
                    root=(tmp_path / "cadrumo-storage").resolve(),
                    binding=profile.binding,
                    secrets_store=native_store,
                )
                before = await asyncio.to_thread(store.snapshot)
                lock_before = await asyncio.to_thread(store.profile_lock_state)
                assert not lock_before.globally_locked
                assert expiry < next(grant.expires_at for grant in before.grants if grant.grant_id == metadata.grant_id)
                # Poll real UTC; neither parent nor immutable worker uses an accelerated clock.
                async with asyncio.timeout(90):
                    while now() <= expiry:
                        await asyncio.sleep(0.25)
                expired_codes = {
                    AccessDenialCode.SESSION_EXPIRED.value,
                    AccessDenialCode.SESSION_INACTIVE.value,
                    AccessDenialCode.CONNECTION_MISMATCH.value,
                }
                try:
                    expired = await asyncio.to_thread(human.status)
                except RuntimeFrontendRefusedError as refusal:
                    assert refusal.reason in expired_codes
                else:
                    assert expired.status.denial is not None
                    assert expired.status.denial.value in expired_codes
                assert await asyncio.to_thread(store.snapshot) == before
                assert await asyncio.to_thread(store.profile_lock_state) == lock_before
            except BaseException as error:
                human_primary = error
                raise
            finally:
                await close_async_resources(
                    human.cleanup_owner(primary_error=human_primary),
                    task_name="expired-human-client-close",
                    primary_error=human_primary,
                )

            # No password or human-administration call follows expiry. Only protected API-reference admission.
            executable = _installed_mcp_executable()
            assert executable.is_file()
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
            with (tmp_path / "installed-after-human-expiry.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters, errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    await sdk.initialize()
                    status_call = await sdk.call_tool("status", {})
                    assert not status_call.is_error
                    status = _status(status_call.structured_content, profile_id=profile.profile_id)
                    assert status.credential_authenticated and status.profile_bound and status.grant_valid
                    assert status.denial is None and status.session_id is not None
                    assert status.session_id != human_session
                    assert status.session_expires_at is not None and status.session_expires_at > now()
                    custody = await asyncio.to_thread(profile.server_custody_health)
                    assert custody.backend is backend and custody.runtime_uses_same_store
                    assert custody.control_anchor_present and custody.wrapping_keys_valid
                    assert metadata.grant_id in custody.grant_ids and metadata.key_id in custody.key_ids
                    health = await asyncio.to_thread(profile.worker_health, status.session_id)
                    assert health.alive and health.exact_session_admitted and health.identity.binding == profile.binding
                    described = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert not described.is_error
                    contract = OperationPublicDefinitionContractV1.model_validate_json(
                        canonical_json_bytes(_object(_object(described.structured_content)["description"])["contract"])
                    )
                    assert contract.definition_id == AUTH_READ_OPERATION_DEFINITION_ID and contract.result_schema
                    submitted = await sdk.call_tool(
                        "execute",
                        {
                            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                            "subject_ref": profile_operation_subject(str(profile.profile_id)),
                            "payload": AuthReadRequest(profile_id=profile.profile_id, kind="status").model_dump(
                                mode="json"
                            ),
                        },
                    )
                    assert not submitted.is_error
                    submission = _object(submitted.structured_content)
                    assert submission["outcome"] == "submitted"
                    receipt = OperationSubmissionReceiptV1.model_validate_json(
                        canonical_json_bytes(submission["receipt"])
                    )
                    observation = OperationObservationRequestV1(
                        operation_id=receipt.operation_id, after_cursor=0, page_limit=32
                    )
                    async with asyncio.timeout(30):
                        while True:
                            observed = await sdk.call_tool(
                                "observe", {"observation": observation.model_dump(mode="json")}
                            )
                            assert not observed.is_error
                            terminal = OperationObservationSuccessV1.model_validate_json(
                                canonical_json_bytes(
                                    _object(_object(observed.structured_content)["reply"])["observation"]
                                )
                            )
                            if terminal.projection.lifecycle is OperationLifecycle.TERMINAL:
                                break
                            await asyncio.sleep(0.05)
                    assert terminal.projection.operation_id == receipt.operation_id
                    assert terminal.projection.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
                    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert terminal.projection.effect is OperationEffect.NONE
                    requested = OperationResultProjectionRequestV1(
                        operation_id=receipt.operation_id,
                        terminal_revision=terminal.projection.revision,
                        definition_contract_digest=contract.definition_contract_digest,
                        result_schema=contract.result_schema,
                    )
                    released = await sdk.call_tool("result", {"result": requested.model_dump(mode="json")})
                    assert not released.is_error
                    result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
                        canonical_json_bytes(_object(released.structured_content)["document"])
                    )
                    assert result.definition_contract_digest == contract.definition_contract_digest
                    assert result.result_schema == contract.result_schema
                    assert result.projection.profile_id == profile.profile_id
                    assert result.projection.kind == "status" and result.projection.status is not None
                    after = await asyncio.to_thread(store.snapshot)
                    assert after.grants == before.grants
                    # Admission may legitimately touch last-used metadata; authority-bearing key facts cannot change.
                    assert tuple(key.model_dump(exclude={"last_used_at"}) for key in after.keys) == tuple(
                        key.model_dump(exclude={"last_used_at"}) for key in before.keys
                    )
                    assert after.automation_enabled == before.automation_enabled
                    assert after.profile_lock_generation == before.profile_lock_generation
                    assert await asyncio.to_thread(store.profile_lock_state) == lock_before
        except BaseException as error:
            primary = error
            raise
        finally:
            await close_async_resources(
                reference_owner, task_name="native-expiry-reference-cleanup", primary_error=primary
            )
