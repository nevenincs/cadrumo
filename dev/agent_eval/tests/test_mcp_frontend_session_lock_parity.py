"""CLI/TUI locks and human proof loss observed by the real MCP SDK.

The encrypted profile, Windows pipe, retained worker Job, application services,
CLI parser and Textual screens are real. OS-login observations and server/client
secret stores are explicit synthetic fixture controls; expiry uses the real clock.
The MCP SDK uses its memory transport, so this is not installed-host acceptance.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.types import CallToolResult
from pydantic import JsonValue
from textual.widgets import Button, Input, Static

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AUTH_READ_RESULT_SCHEMA_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    AuthorityState,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.conftest import authority_operation
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.json_contract import SchemaEnvelope
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.cli.config.runtime_access_management_payloads import (
    ConfigProfileLockResult,
    ConfigProfileSessionsResult,
)
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.runtime_access_management import RuntimeAccessManagementScreen
from cadrumo.entrypoints.tui.secret.automation_requester import RuntimeAutomationRequesterScreen
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

__all__ = ["authority_operation"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass
class _LoginObservation:
    login_id: str
    active: bool = True

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=self.active,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE if self.active else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass
class _ParityRuntime:
    subject: AdministrationSubject
    profiles: RuntimeProfileConnections
    reference: UUID
    origin: _LoginObservation
    independent: _LoginObservation
    capture: list[_LoginObservation]

    @property
    def profile_id(self) -> UUID:
        return self.subject.store.binding.profile_id

    def assert_worker_contained(self) -> None:
        """Verify the actual retained Job owns this exact authenticated worker peer."""
        with self.profiles._guard:
            worker = self.profiles._profiles[self.profile_id].owner.operation_worker()
            worker.require_alive()
            channel = worker._channel
            assert channel is not None and channel.peer.process_id is not None
            assert channel.peer.os_owner_id == owner_id()
            assert channel.peer.process_id in worker._scope.active_process_ids()
            assert worker._owns_native_process(channel.peer.process_id)


def _scope(destination: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({AUTH_READ_OPERATION_DEFINITION_ID}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=AUTH_READ_RESULT_SCHEMA_ID,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            }
        ),
        periods=frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )


@contextmanager
def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_ParityRuntime]:
    # The isolated worker loads settings independently of this process's override context.
    monkeypatch.setenv("CADRUMO_BUCKET_DEFAULT_IDLE_LOCK_MINUTES", "1")
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(
            cadrumo_local_storage_root=root,
            cadrumo_output_language="en",
            cadrumo_cli_reveal_identifiers=True,
            cadrumo_profile_kdf_measure_calibration=False,
            cadrumo_bucket_default_idle_lock_minutes=1,
        ),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject,
    ):
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        scope = _scope(requester.client_id)
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        request_id = uuid4()
        subject.service.request(request_id, changed(subject.proposal, scope=scope))
        approved = subject.approve(request_id)
        assert approved.credential_reference is not None
        close_active_bucket_session()
        delete_profile_session(storage_root=root, profile_id=subject.store.binding.profile_id)
        origin, independent = _LoginObservation("parity-origin"), _LoginObservation("parity-independent")
        capture = [origin]
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: capture[0],
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        # Only the installed client-store composition is substituted; admission remains real.
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
        owner.executor = ThreadPoolExecutor(max_workers=1)
        primary: BaseException | None = None
        try:
            context = copy_context()

            def serve() -> None:
                context.run(server.serve)

            owner.server = server
            owner.running = owner.executor.submit(serve)
            assert server.ready.wait(3)
            yield _ParityRuntime(subject, profiles, approved.credential_reference, origin, independent, capture)
        except BaseException as error:
            primary = error
            raise
        finally:
            owner.close_from_sync(task_name="mcp-frontend-lock-runtime-close", primary_error=primary)


def _structured(reply: CallToolResult) -> dict[str, JsonValue]:
    assert isinstance(reply.structured_content, dict)
    return cast("dict[str, JsonValue]", reply.structured_content)


async def _authenticate(sdk: ClientSession, runtime: _ParityRuntime) -> ProfileAccessStatus:
    reply = await sdk.call_tool("authenticate", {"credential_reference": str(runtime.reference)})
    assert not reply.is_error, _structured(reply)
    value = _structured(reply)
    assert value["outcome"] == "authenticated"
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(value["status"]))
    assert status.profile_id == runtime.profile_id and status.grant_valid and status.denial is None
    assert status.session_id is not None
    assert str(runtime.reference) not in repr(value)
    return status


async def _private_read(sdk: ClientSession, profile_id: UUID) -> OperationResultProjectionRequestV1:
    described = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
    assert not described.is_error, _structured(described)
    description = _structured(described)["description"]
    assert isinstance(description, dict)
    contract = OperationPublicDefinitionContractV1.model_validate_json(canonical_json_bytes(description["contract"]))
    assert contract.result_schema is not None
    request = AuthReadRequest(profile_id=profile_id, kind="status")
    submitted = await sdk.call_tool(
        "execute",
        {
            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert not submitted.is_error, _structured(submitted)
    receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(_structured(submitted)["receipt"]))
    observation = OperationObservationRequestV1(operation_id=receipt.operation_id, after_cursor=0, page_limit=32)
    async with asyncio.timeout(60):
        while True:
            observed = await sdk.call_tool("observe", {"observation": observation.model_dump(mode="json")})
            assert not observed.is_error, _structured(observed)
            reply = _structured(observed)["reply"]
            assert isinstance(reply, dict)
            terminal = OperationObservationSuccessV1.model_validate_json(canonical_json_bytes(reply["observation"]))
            if terminal.projection.lifecycle is OperationLifecycle.TERMINAL:
                break
            await asyncio.sleep(0.05)
    assert terminal.projection.operation_id == receipt.operation_id
    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.projection.effect is OperationEffect.NONE
    result = OperationResultProjectionRequestV1(
        operation_id=receipt.operation_id,
        terminal_revision=terminal.projection.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )
    released = await sdk.call_tool("result", {"result": result.model_dump(mode="json")})
    assert not released.is_error, _structured(released)
    document = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
        canonical_json_bytes(_structured(released)["document"])
    )
    assert document.definition_contract_digest == contract.definition_contract_digest
    assert document.result_schema == contract.result_schema
    assert document.projection.profile_id == profile_id and document.projection.kind == "status"
    assert document.projection.status is not None
    return result


def _cli_lock(runtime: _ParityRuntime, *, global_lock: bool, human: bool) -> ConfigProfileLockResult:
    options = (
        ("--profile-secrets-stdin",)
        if human
        else ("--profile-auth-method", "api-key", "--profile-credential-ref", str(runtime.reference))
    )
    result = invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            str(runtime.profile_id),
            *options,
            "config",
            "profile",
            "lock",
            *(("--all",) if global_lock else ()),
        ),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}) if human else None,
    )
    assert result.exit_code == 0, result.output
    assert PROFILE_INPUT not in result.output and str(runtime.reference) not in result.output
    envelope = SchemaEnvelope[ConfigProfileLockResult].model_validate_json(result.stdout)
    assert envelope.command == "config.profile.lock"
    return envelope.result


@pytest.mark.anyio
@pytest.mark.parametrize("proof_loss", ["expiry", "originating_login"])
async def test_cli_own_lock_and_human_proof_loss_preserve_independent_mcp_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proof_loss: Literal["expiry", "originating_login"]
) -> None:
    """Human retirement cannot revoke the independently enrolled MCP authority."""
    with _runtime(tmp_path, monkeypatch) as runtime:
        human = await open_installed_runtime_client(
            profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI
        )
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=None)
        primary: BaseException | None = None
        try:
            password = bytearray(PROFILE_INPUT.encode())
            admitted = await asyncio.to_thread(human.login_password, password)
            assert not any(password)
            human_id = human.session_id
            runtime.capture[0] = runtime.independent
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                first = await _authenticate(sdk, runtime)
                await _private_read(sdk, runtime.profile_id)
                runtime.assert_worker_contained()
                before = runtime.subject.store.snapshot()
                enrollment_before = runtime.subject.store.enrollment_state()
                lock_before = runtime.subject.store.profile_lock_state()
                locked = await asyncio.to_thread(_cli_lock, runtime, global_lock=False, human=False)
                assert locked.scope == "current" and locked.denial is None
                assert len(locked.session_ids) == 1 and first.session_id not in locked.session_ids
                assert runtime.subject.store.snapshot() == before
                assert runtime.subject.store.enrollment_state() == enrollment_before
                assert runtime.subject.store.profile_lock_state() == lock_before
                factories: list[RuntimeFrontendClient] = []

                async def no_recovery() -> RuntimeFrontendClient:
                    raise AssertionError("lost human authority must not silently acquire password proof")

                def no_requester(client: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
                    factories.append(client)
                    raise AssertionError("lost human authority must not create an enrollment requester")

                screen = RuntimeAccessManagementScreen(
                    human, open_recovery_client=no_recovery, requester_factory=no_requester
                )
                app = ScreenHostApp(screen)
                async with app.run_test(size=(140, 48)) as pilot:
                    async with asyncio.timeout(30):
                        while not screen._admin_available and not screen.access_lost:
                            await pilot.pause(0.05)
                    await asyncio.wait_for(app.workers.wait_for_complete(), 30)
                    assert screen._admin_available and not screen.access_lost
                    assert str(first.session_id) in str(screen.query_one("#runtime-access-sessions", Static).content)
                    if proof_loss == "expiry":
                        assert admitted.status.session_expires_at is not None
                        assert first.session_expires_at is not None
                        assert admitted.status.session_expires_at < first.session_expires_at
                        async with asyncio.timeout(90):
                            while now() < admitted.status.session_expires_at:
                                await asyncio.sleep(0.2)
                    else:
                        runtime.origin.active = False
                    screen.query_one("#runtime-access-refresh", Button).press()
                    await pilot.pause()
                    await asyncio.wait_for(app.workers.wait_for_complete(), 30)
                    assert screen.access_lost and not screen._admin_available
                    assert not screen.query_one("#runtime-access-sessions", Static).content
                    screen.on_button_pressed(
                        Button.Pressed(screen.query_one("#runtime-access-create-automation", Button))
                    )
                    assert not factories
                    with pytest.raises(RuntimeFrontendRefusedError):
                        await asyncio.to_thread(human.deny_automation, AutomationDenialKind.ALL)
                    assert runtime.subject.store.snapshot() == before
                    assert runtime.subject.store.enrollment_state() == enrollment_before
                    assert runtime.subject.store.profile_lock_state() == lock_before
                    screen.action_close()
                    await pilot.pause()
                await _private_read(sdk, runtime.profile_id)
                live = await sdk.call_tool("status", {})
                assert not live.is_error, _structured(live)
                live_status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(_structured(live)["status"]))
                assert live_status.session_id == first.session_id and live_status.grant_valid
                # Reconnect from the same protected root key without a human password.
                fresh = await _authenticate(sdk, runtime)
                assert fresh.session_id != first.session_id and fresh.session_id != human_id
                await _private_read(sdk, runtime.profile_id)
                cli = await asyncio.to_thread(
                    invoke_cached_cli,
                    (
                        "--format",
                        "json",
                        "--profile",
                        str(runtime.profile_id),
                        "--profile-secrets-stdin",
                        "config",
                        "profile",
                        "sessions",
                    ),
                    input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
                )
                assert cli.exit_code == 0, cli.output
                assert PROFILE_INPUT not in cli.output
                inventory = SchemaEnvelope[ConfigProfileSessionsResult].model_validate_json(cli.stdout).result
                assert any(item.session_id == fresh.session_id for item in inventory.sessions)
                assert all(item.session_id != human_id for item in inventory.sessions)
        except BaseException as error:
            primary = error
            raise
        finally:
            await close_async_resources(
                adapter,
                human.cleanup_owner(primary_error=primary),
                task_name="human-proof-loss-frontends-close",
                primary_error=primary,
            )


@pytest.mark.anyio
async def test_cli_global_lock_fences_tui_mcp_and_password_login_cannot_clear_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A normal password login cannot bypass explicit global suspension or reactivate grants."""
    with _runtime(tmp_path, monkeypatch) as runtime:
        human = await open_installed_runtime_client(
            profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI
        )
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=None)
        other_clients: list[RuntimeFrontendClient] = []
        primary: BaseException | None = None
        try:
            password = bytearray(PROFILE_INPUT.encode())
            await asyncio.to_thread(human.login_password, password)
            assert not any(password)
            runtime.capture[0] = runtime.independent
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                await _authenticate(sdk, runtime)
                private_result = await _private_read(sdk, runtime.profile_id)
                runtime.assert_worker_contained()
                before = runtime.subject.store.snapshot()
                lock_before = runtime.subject.store.profile_lock_state()
                locked = await asyncio.to_thread(_cli_lock, runtime, global_lock=True, human=True)
                assert locked.scope == "profile" and locked.denial is not None and locked.denial.access_denied
                suspended = runtime.subject.store.snapshot()
                global_lock = runtime.subject.store.profile_lock_state()
                assert global_lock.globally_locked and global_lock.generation == lock_before.generation + 1
                assert suspended.grants == tuple(
                    changed(grant, state=AuthorityState.SUSPENDED, generation=grant.generation + 1)
                    for grant in before.grants
                )
                assert suspended.keys == tuple(
                    changed(key, state=AuthorityState.SUSPENDED, generation=key.generation + 1) for key in before.keys
                )
                enrollment_suspended = runtime.subject.store.enrollment_state()
                refused = await sdk.call_tool("result", {"result": private_result.model_dump(mode="json")})
                assert refused.is_error and _structured(refused)["outcome"] == "refused"
                fresh_api = await sdk.call_tool("authenticate", {"credential_reference": str(runtime.reference)})
                assert fresh_api.is_error and _structured(fresh_api)["outcome"] == "refused"
                fresh_human = await open_installed_runtime_client(
                    profile_id=runtime.profile_id, frontend=OperationFrontendProjection.TUI
                )
                other_clients.append(fresh_human)
                password = bytearray(PROFILE_INPUT.encode())
                with pytest.raises(RuntimeFrontendRefusedError) as login_denied:
                    await asyncio.to_thread(fresh_human.login_password, password)
                assert login_denied.value.reason == AccessDenialCode.PROFILE_LOCKED.value
                assert not any(password)
                factories: list[RuntimeFrontendClient] = []

                async def no_recovery() -> RuntimeFrontendClient:
                    raise AssertionError("global unlock requires a separate explicit password recovery")

                def no_requester(client: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
                    factories.append(client)
                    raise AssertionError("globally locked authority must not create enrollment")

                screen = RuntimeAccessManagementScreen(
                    human, open_recovery_client=no_recovery, requester_factory=no_requester
                )
                app = ScreenHostApp(screen)
                async with app.run_test(size=(140, 48)) as pilot:
                    async with asyncio.timeout(30):
                        while not screen.access_lost:
                            await pilot.pause(0.05)
                    await asyncio.wait_for(app.workers.wait_for_complete(), 30)
                    assert screen.access_lost and not screen._admin_available
                    assert not screen.query_one("#runtime-access-sessions", Static).content
                    screen.on_button_pressed(
                        Button.Pressed(screen.query_one("#runtime-access-create-automation", Button))
                    )
                    screen.query_one("#runtime-access-target", Input).value = str(suspended.keys[0].key_id)
                    screen.on_button_pressed(Button.Pressed(screen.query_one("#runtime-access-deny-key", Button)))
                    await asyncio.wait_for(app.workers.wait_for_complete(), 30)
                    assert not factories
                    assert runtime.subject.store.snapshot() == suspended
                    assert runtime.subject.store.enrollment_state() == enrollment_suspended
                    assert runtime.subject.store.profile_lock_state() == global_lock
                    screen.action_close()
        except BaseException as error:
            primary = error
            raise
        finally:
            await close_async_resources(
                adapter,
                *(client.cleanup_owner(primary_error=primary) for client in reversed(other_clients)),
                human.cleanup_owner(primary_error=primary),
                task_name="global-lock-frontends-close",
                primary_error=primary,
            )
