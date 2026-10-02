"""Installed Windows supervision and explicit-demand recovery with real native credentials.

Only initial profile/grant preparation uses synthetic human provenance. Both
installed boots, SDK admissions and private workers are real; no write replay or
browser-containment inference is made by this AuthRead case.
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import AsyncExitStack
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests import windows_managed_runtime_fixture as task_fixture
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_delivery import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.automation_store import (
    CONTROL_NAMESPACE,
    WRAP_NAMESPACE,
    retire_profile_automation,
)
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeManagerProcessState
from cadrumo.application.runtime.profile_access import (
    PROFILE_ADMISSION_TIMEOUT_SECONDS,
    RuntimeAccessRefusal,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from cadrumo.application.runtime.transport import RuntimeStatusRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationSecretStore,
    NativeSecretBackend,
)
from cadrumo.core.async_cleanup import async_cleanup_failures, await_cancellation_complete, close_async_resources
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path

from .test_installed_authenticated_stdio import _installed_mcp_executable, _scope_for_auth_read
from .test_installed_mcp_tui_grant_parity import _private_read, _record, _status

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires the installed Windows runtime and normal desktop"),
]


class _SdkCleanup:
    """Retain the original SDK context stack until its complete close succeeds."""

    def __init__(self, stack: AsyncExitStack) -> None:
        self.stack, self.released = stack, False
        self.failure: BaseException | None = None

    async def close(self) -> None:
        if self.released:
            return
        if self.failure is not None:
            owners = {
                id(owner): owner for failure in async_cleanup_failures(self.failure) for owner in failure.resources
            }
            if not owners:
                raise self.failure
            await close_async_resources(*owners.values(), task_name="recovery-sdk-retained-close", primary_error=None)
        else:
            try:
                await self.stack.aclose()
            except BaseException as error:
                self.failure = error
                raise
        self.released = True


class _ClientCredentialCleanup:
    """Delete only this test's published recipient entries after physical task retirement."""

    def __init__(
        self, subject: AdministrationSubject, protected: NativeClientCredentialStore, request_id: UUID
    ) -> None:
        self.subject, self.protected, self.request_id = subject, protected, request_id
        self.task: task_fixture.InstalledWindowsRuntimeTask | None = None
        self.released = False

    async def close(self) -> None:
        if self.released:
            return
        if self.task is not None and not self.task.cleanup.released:
            raise RuntimeError("native credentials remain owned by an unsettled runtime task")

        def delete() -> None:
            for record in self.subject.store.enrollment_state().requests:
                if (
                    record.request_id == self.request_id
                    and record.credential_reference is not None
                    and record.candidate_key_id is not None
                ):
                    self.protected.delete(
                        credential_reference=record.credential_reference,
                        grant_id=record.grant_id,
                        key_id=record.candidate_key_id,
                        review_digest=enrollment_review_digest(record),
                    )

        await asyncio.to_thread(delete)
        self.released = True


class _ServerCustodyCleanup:
    """Retire this exact synthetic server custody only after the task owner settles."""

    def __init__(self, subject: AdministrationSubject, native: AutomationSecretStore, root: Path) -> None:
        self.subject, self.native, self.root = subject, native, root
        self.task: task_fixture.InstalledWindowsRuntimeTask | None = None
        self.released = False

    async def close(self) -> None:
        if self.released:
            return
        if self.task is not None and not self.task.cleanup.released:
            raise RuntimeError("server custody remains owned by an unsettled runtime task")

        def retire() -> None:
            assert retire_profile_automation(
                root=self.root, profile_id=self.subject.store.binding.profile_id, secrets_store=self.native
            )

        await asyncio.to_thread(retire)
        self.released = True


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery", ["autonomous-crash", "demand-after-stop"])
async def test_installed_windows_sdk_reconnects_with_exact_runtime_recovery(tmp_path: Path, recovery: str) -> None:
    """Native protected credentials survive a lost boot; recovery modes have distinct task identities."""
    require_selected_normal_desktop()
    mcp_executable = _installed_mcp_executable()
    assert mcp_executable.is_file(), "requires the inspected installed build"
    root = (tmp_path / "cadrumo-storage").resolve()
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=endpoint.os_owner_id, storage_identity=endpoint.storage_identity
    )
    endpoint_owner = RuntimeTransportCleanup(endpoint)
    native = native_automation_secret_store(NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER)
    assert native.backend is NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER
    with administration_subject(
        tmp_path,
        os_owner_id=endpoint.os_owner_id,
        installation_id=installation.installation_id,
        profile_label="Installed runtime recovery",
    ) as subject:
        assert native.read(CONTROL_NAMESPACE, subject.store.account) is None
        subject.store.secrets = native
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(requester=requester, secrets_store=native)
        scope = _scope_for_auth_read(requester.client_id)
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
        )
        subject.proposal = changed(subject.proposal, scope=scope)
        request_id = uuid4()
        protected = NativeClientCredentialStore(
            secrets_store=native,
            binding=subject.store.binding,
            client_id=requester.client_id,
            destination_id=requester.destination_id,
        )
        client_owner = _ClientCredentialCleanup(subject, protected, request_id)
        server_owner = _ServerCustodyCleanup(subject, native, root)
        sdk_resources = AsyncExitStack()
        sdk_owner = _SdkCleanup(sdk_resources)
        sdk_owners = [sdk_owner]
        primary: BaseException | None = None
        try:
            subject.service.request(request_id, subject.proposal)
            receipt = subject.approve(request_id)
            assert receipt.credential_reference is not None and receipt.key_id is not None
            metadata = protected.inspect(credential_reference=receipt.credential_reference)
            assert (metadata.grant_id, metadata.key_id) == (receipt.grant_id, receipt.key_id)
            initial_payload = subject.store.read()[1]
            grant = next(entry.grant for entry in initial_payload.grants if entry.grant.grant_id == metadata.grant_id)
            wrap_accounts = tuple(
                subject.store.account + "/" + str(entry.wrap_key_id)
                for entry in initial_payload.grants
                if entry.wrap_key_id is not None
            )
            close_active_bucket_session()
            parameters = StdioServerParameters(
                command=str(mcp_executable),
                args=[
                    "--profile-id",
                    str(metadata.profile_id),
                    "--credential-reference",
                    str(metadata.credential_reference),
                ],
                cwd=tmp_path,
                env={
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
                    "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                    "PYDANTIC_DISABLE_PLUGINS": "__all__",
                },
            )
            async with task_fixture.installed_windows_runtime_task(tmp_path, storage_root=root) as task:
                client_owner.task, server_owner.task = task, task
                task.mark_launch_possible()
                identity = task_fixture.installed_windows_task_identity(task.task_name, task.binding)
                assert identity is not None
                assert (await task.manager.inspect()).process_state is RuntimeManagerProcessState.STOPPED
                with (tmp_path / "first-sdk-stderr.txt").open("w", encoding="utf-8") as errlog:
                    read, write = await sdk_resources.enter_async_context(stdio_client(parameters, errlog=errlog))
                    first = await sdk_resources.enter_async_context(
                        ClientSession(read, write, read_timeout_seconds=PROFILE_ADMISSION_TIMEOUT_SECONDS + 5)
                    )
                    await first.initialize()
                    first_status = _status(
                        _record((await first.call_tool("status", {})).structured_content), metadata.profile_id
                    )
                    assert first_status.effective_scope == scope
                    first_result = await _private_read(first, metadata.profile_id)
                    observed, first_boot = await task.observe_live_process()
                    first_guid, first_engine = await asyncio.to_thread(
                        task_fixture.installed_windows_task_instance,
                        task.binding,
                        task.task_name,
                        identity,
                        observed.pid,
                    )
                    engine = await await_cancellation_complete(
                        asyncio.to_thread(task_fixture.retain_windows_task_engine, first_engine, task.cleanup),
                        task_name="recovery-native-handle-capture",
                    )
                    first_tree = await await_cancellation_complete(
                        asyncio.to_thread(
                            task_fixture.retain_windows_runtime_tree,
                            observed.pid,
                            task.cleanup,
                            engine_pid=first_engine if recovery == "demand-after-stop" else None,
                        ),
                        task_name="recovery-native-handle-capture",
                    )
                    actual_runtime = next(process for process in first_tree if process.pid == observed.pid)
                    old_probe = task.control
                    assert old_probe is not None and engine.alive() and all(process.alive() for process in first_tree)
                    if recovery == "autonomous-crash":
                        actual_runtime.terminate()
                        await task_fixture.wait_windows_recovery_processes_gone(first_tree, timeout=17)
                        assert engine.alive()
                        replacement_host, replacement_boot = await task.observe_replacement_process(
                            actual_runtime, first_boot, deadline=time.monotonic() + 90
                        )
                        assert replacement_boot != first_boot
                        replacement_guid, replacement_engine = await asyncio.to_thread(
                            task_fixture.installed_windows_task_instance,
                            task.binding,
                            task.task_name,
                            identity,
                            replacement_host.pid,
                        )
                        assert replacement_guid == first_guid and replacement_engine == first_engine
                        assert engine.alive()
                    else:
                        await task.prepare_physical_cleanup()
                        assert task.stop_accepted is not None and task.stop_accepted.runtime_boot_id == first_boot
                        await task_fixture.wait_windows_recovery_processes_gone(first_tree, timeout=25)
                        await asyncio.to_thread(engine.wait, timeout=25)
                        assert not engine.alive()
                        assert (await task.manager.inspect()).process_state is RuntimeManagerProcessState.STOPPED
                    status_failures: list[BaseException] = []

                    def read_old_status() -> None:
                        try:
                            old_probe.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 5)
                        except BaseException as error:
                            task.retain_transport_cleanup(error)
                            status_failures.append(error)

                    with pytest.raises(RuntimeRefusalError) as closed:
                        try:
                            await await_cancellation_complete(
                                asyncio.to_thread(read_old_status), task_name="recovery-retired-status-exchange"
                            )
                        except asyncio.CancelledError as primary:
                            if status_failures:

                                async def failed_status() -> None:
                                    raise status_failures[0]

                                await await_cancellation_complete(
                                    failed_status(),
                                    cancellation=primary,
                                    task_name="recovery-status-failure-diagnostic",
                                )
                            raise
                        if status_failures:
                            raise status_failures[0]
                    assert closed.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
                    if recovery == "autonomous-crash":
                        retired = await first.call_tool("result", {"result": first_result.model_dump(mode="json")})
                        refused = _record(retired.structured_content)
                        assert retired.is_error and refused["outcome"] == "refused", refused
                        assert refused["code"] in {
                            RuntimeRefusalCode.CONNECTION_CLOSED.value,
                            AccessDenialCode.SESSION_INACTIVE.value,
                            AccessDenialCode.CONNECTION_MISMATCH.value,
                        }
                    await close_async_resources(sdk_owner, task_name="recovery-first-sdk-close", primary_error=None)
                if recovery == "demand-after-stop":
                    # A completed intentional Stop permits a distinct explicit demand.
                    task.control, task.runtime_boot = None, None
                    task.stop_dispatched, task.stop_accepted, task.stop_failure = False, None, None
                assert not (await task.manager.inspect()).login_autostart
                sdk_resources = AsyncExitStack()
                sdk_owner = _SdkCleanup(sdk_resources)
                sdk_owners.append(sdk_owner)
                with (tmp_path / "replacement-sdk-stderr.txt").open("w", encoding="utf-8") as errlog:
                    read, write = await sdk_resources.enter_async_context(stdio_client(parameters, errlog=errlog))
                    replacement = await sdk_resources.enter_async_context(
                        ClientSession(read, write, read_timeout_seconds=PROFILE_ADMISSION_TIMEOUT_SECONDS + 5)
                    )
                    await replacement.initialize()
                    replacement_status = _status(
                        _record((await replacement.call_tool("status", {})).structured_content), metadata.profile_id
                    )
                    assert replacement_status.session_id != first_status.session_id
                    assert replacement_status.effective_scope == scope
                    second_result = await _private_read(replacement, metadata.profile_id)
                    assert second_result.operation_id != first_result.operation_id
                    assert second_result.definition_contract_digest == first_result.definition_contract_digest
                    assert second_result.result_schema == first_result.result_schema
                    second_host, second_boot = await task.observe_live_process()
                    assert second_boot != first_boot
                    second_guid, second_engine = await asyncio.to_thread(
                        task_fixture.installed_windows_task_instance,
                        task.binding,
                        task.task_name,
                        identity,
                        second_host.pid,
                    )
                    if recovery == "autonomous-crash":
                        assert second_guid == first_guid and second_engine == first_engine and engine.alive()
                    else:
                        assert second_guid != first_guid
                    second_tree = await await_cancellation_complete(
                        asyncio.to_thread(
                            task_fixture.retain_windows_runtime_tree,
                            second_host.pid,
                            task.cleanup,
                            engine_pid=second_engine,
                        ),
                        task_name="recovery-native-handle-capture",
                    )
                    assert first_status.session_id is not None
                    first_session_id = first_status.session_id
                    new_probe = task.control
                    assert new_probe is not None
                    session_failures: list[BaseException] = []
                    session_values: list[RuntimeProfileStatus | RuntimeSessionsLocked | RuntimeAccessRefusal] = []

                    def read_stale_session() -> None:
                        try:
                            session_values.append(
                                new_probe.session(
                                    RuntimeSessionRequest(
                                        action="session_status",
                                        request_id=uuid4(),
                                        profile_id=metadata.profile_id,
                                        session_id=first_session_id,
                                    ),
                                    deadline=time.monotonic() + 5,
                                )
                            )
                        except BaseException as error:
                            task.retain_transport_cleanup(error)
                            session_failures.append(error)

                    try:
                        await await_cancellation_complete(
                            asyncio.to_thread(read_stale_session), task_name="recovery-stale-lease-exchange"
                        )
                    except asyncio.CancelledError as primary:
                        if session_failures:

                            async def failed_session() -> None:
                                raise session_failures[0]

                            await await_cancellation_complete(
                                failed_session(), cancellation=primary, task_name="recovery-session-failure-diagnostic"
                            )
                        raise
                    if session_failures:
                        raise session_failures[0]
                    stale = session_values[0]
                    assert isinstance(stale, RuntimeAccessRefusal)
                    assert stale.code is AutomationCustodyCode.CREDENTIAL_REJECTED
                    assert protected.inspect(credential_reference=metadata.credential_reference) == metadata
                    current = subject.store.read()[1]
                    assert (
                        next(entry.grant for entry in current.grants if entry.grant.grant_id == metadata.grant_id)
                        == grant
                    )
                    inspection = await task.manager.inspect()
                    assert inspection.binding_matches and not inspection.login_autostart
                    await close_async_resources(
                        sdk_owner, task_name="recovery-replacement-sdk-close", primary_error=None
                    )
                    # Session traffic used the previous probe; retain a fresh owner-control channel.
                    task.control = None
                    owner_host, owner_boot = await task.observe_live_process()
                    assert owner_boot == second_boot
                    assert owner_host.pid == second_host.pid
                    await task.prepare_physical_cleanup()
                    assert task.stop_accepted is not None and task.stop_accepted.runtime_boot_id == second_boot
                    await task_fixture.wait_windows_recovery_processes_gone(second_tree, timeout=25)
                assert not any(process.alive() for process in first_tree)
        except BaseException as error:
            primary = error
            raise
        finally:
            await close_async_resources(
                *sdk_owners,
                client_owner,
                server_owner,
                endpoint_owner,
                task_name="installed-recovery-custody-close",
                primary_error=primary,
            )
        assert native.read(CONTROL_NAMESPACE, subject.store.account) is None
        assert all(native.read(WRAP_NAMESPACE, account) is None for account in wrap_accounts)
