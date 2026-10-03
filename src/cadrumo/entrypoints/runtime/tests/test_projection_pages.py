"""Native result paging retains canonical projection and per-page authority."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Literal
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationPage,
    RuntimeOperationProjected,
    RuntimeOperationReply,
    RuntimeOperationResult,
    RuntimeOperationResultPage,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.runtime.projection_pages import PROJECTION_PAGE_BYTES, ProjectionPageRequest
from cadrumo.application.runtime.worker_authorization import WorkerAuthorityRequest
from cadrumo.application.user_profile.automation_enrollment import AutomationInventoryProjection
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.automation_operations import (
    AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
    AutomationOperationRequest,
)
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.operations import OperationTerminalCondition

from .. import profile_connection_operations
from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection, RuntimeProfileHost
from .operation_transport_support import PausedProjectionListener, ProjectionWriteBarrier
from .test_automation_enrollment import _connect, _LoginObservation, _submit_operation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@dataclass
class _NativeProjectionRace:
    """Real encrypted persistence and native IPC; login/store controls are synthetic."""

    raw: VerifiedRuntimeConnection
    control: RuntimeFrontendClient
    profiles: RuntimeProfileConnections
    pool: ThreadPoolExecutor
    barrier: ProjectionWriteBarrier
    profile_id: UUID
    session_id: UUID
    result: OperationResultProjectionRequestV1
    expected_document: bytes
    journal: OperationJournalRepository
    terminal: OperationPersistedSnapshot

    def request(
        self, projection_kind: Literal["result", "page"]
    ) -> RuntimeOperationResult | RuntimeOperationResultPage:
        if projection_kind == "result":
            return RuntimeOperationResult(
                request_id=uuid4(), profile_id=self.profile_id, session_id=self.session_id, result=self.result
            )
        return RuntimeOperationResultPage(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self.session_id,
            result=self.result,
            page=ProjectionPageRequest(),
        )

    def assert_projection(self, reply: RuntimeOperationReply | RuntimeAccessRefusal) -> None:
        assert isinstance(reply, RuntimeOperationProjected | RuntimeOperationPage), reply
        assert reply.operation_id == self.result.operation_id
        if isinstance(reply, RuntimeOperationPage):
            assert reply.page.offset == 0
            assert reply.page.total_bytes == len(self.expected_document)
            assert reply.page.document_digest == sha256_hex(self.expected_document)
            encoded = reply.page.decode()
        else:
            assert reply.projection_kind == "result"
            encoded = canonical_json_bytes(reply.document)
        assert encoded == self.expected_document
        projected = OperationResultProjectionSuccessV1[AutomationInventoryProjection].model_validate_json(encoded)
        assert projected.result_schema == self.result.result_schema
        assert projected.definition_contract_digest == self.result.definition_contract_digest

    def assert_terminal_unchanged(self) -> None:
        # A denial fences disclosure; it cannot rewrite a settled operation's truth.
        assert asyncio.run(self.journal.load(self.result.operation_id)) == self.terminal
        assert self.terminal.revision == self.result.terminal_revision
        assert self.terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert self.terminal.terminal_receipt is not None


@pytest.fixture
def native_projection_race(tmp_path: Path) -> Generator[_NativeProjectionRace]:
    """Reuse the native paging cohort without claiming genuine OS-store acceptance."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        pending_request = uuid4()
        subject.service.request(pending_request, subject.proposal)
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        barrier = ProjectionWriteBarrier()
        server = RuntimeTransportServer(
            PausedProjectionListener(endpoint, barrier),
            product_version="test",
            stop=stop,
            profiles=profiles,
            boot_id=boot,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    raw = _connect(endpoint)
                    cleanup.callback(raw.close)
                    client = RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
                    cleanup.callback(client.close)
                    control_raw = _connect(endpoint)
                    cleanup.callback(control_raw.close)
                    control = RuntimeFrontendClient(
                        control_raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                    )
                    cleanup.callback(control.close)
                    # Release a paused native write before clients/server are closed on any failure.
                    cleanup.callback(barrier.release.set)
                    client.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    control.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    assert client.session_id is not None
                    contract, submitted, observed = _submit_operation(
                        raw,
                        profile_id=profile_id,
                        session_id=client.session_id,
                        definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
                    )
                    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    schema = contract.contract.result_schema
                    assert schema is not None
                    result = OperationResultProjectionRequestV1(
                        operation_id=submitted.receipt.operation_id,
                        terminal_revision=observed.projection.revision,
                        definition_contract_digest=contract.contract.definition_contract_digest,
                        result_schema=schema,
                    )
                    encoded = canonical_json_bytes(client.read_result_document(result, timeout=30))
                    assert len(encoded) <= PROJECTION_PAGE_BYTES
                    projected = OperationResultProjectionSuccessV1[AutomationInventoryProjection].model_validate_json(
                        encoded
                    )
                    assert {item.receipt.request_id for item in projected.projection.requests} == {pending_request}
                    journal = OperationJournalRepository(storage_root=root)
                    terminal = asyncio.run(journal.load(result.operation_id))
                    yield _NativeProjectionRace(
                        raw=raw,
                        control=control,
                        profiles=profiles,
                        pool=pool,
                        barrier=barrier,
                        profile_id=profile_id,
                        session_id=client.session_id,
                        result=result,
                        expected_document=encoded,
                        journal=journal,
                        terminal=terminal,
                    )
            finally:
                primary = sys.exception()
                barrier.release.set()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()


@pytest.mark.parametrize("projection_kind", ["result", "page"])
def test_native_projection_denies_revoke_after_worker_before_parent_guard(
    native_projection_race: _NativeProjectionRace,
    monkeypatch: pytest.MonkeyPatch,
    projection_kind: Literal["result", "page"],
) -> None:
    subject = native_projection_race
    request = subject.request(projection_kind)
    worker_returned, release_parent = Event(), Event()
    original_prepare = profile_connection_operations.prepare_operation_projection

    def pause_after_worker(
        host: RuntimeProfileHost,
        connection: ProfileConnection,
        selected: RuntimeOperationResult | RuntimeOperationResultPage,
    ) -> tuple[RuntimeOperationReply, WorkerAuthorityRequest]:
        prepared = original_prepare(host, connection, selected)
        if selected.request_id == request.request_id:
            subject.assert_projection(prepared[0])
            assert prepared[1].operation_id == subject.result.operation_id
            worker_returned.set()
            assert release_parent.wait(5), "parent disclosure barrier exceeded its bounded wait"
        return prepared

    subject.barrier.reply_kind = "operation_projected" if projection_kind == "result" else "operation_page"
    subject.barrier.request_id = request.request_id
    subject.barrier.release.set()  # Observe actual writes without introducing a second pause.
    subject.barrier.enabled.set()
    # Patch only the timing boundary in this isolated fixture, calling its real worker owner.
    monkeypatch.setattr(profile_connection_operations, "prepare_operation_projection", pause_after_worker)
    reading = subject.pool.submit(subject.raw.operation, request, deadline=time.monotonic() + 10)
    try:
        assert worker_returned.wait(3), "real worker projection did not reach the parent boundary"
        denied = subject.control.deny_automation(AutomationDenialKind.PROFILE_LOCK, timeout=5)
        assert denied.profile_id == subject.profile_id and denied.access_denied
        assert subject.barrier.denial_written.wait(3)
        assert subject.barrier.events() == ("denial_received", "denial_written")
        release_parent.set()
        reply = reading.result(timeout=5)
        assert isinstance(reply, RuntimeAccessRefusal), reply
        assert reply.request_id == request.request_id
        assert subject.barrier.events() == ("denial_received", "denial_written")
        assert isinstance(
            subject.raw.operation(subject.request(projection_kind), deadline=time.monotonic() + 5),
            RuntimeAccessRefusal,
        )
        subject.assert_terminal_unchanged()
    finally:
        release_parent.set()
        subject.barrier.release.set()


@pytest.mark.parametrize("projection_kind", ["result", "page"])
def test_native_projection_final_write_serializes_profile_revoke(
    native_projection_race: _NativeProjectionRace,
    projection_kind: Literal["result", "page"],
) -> None:
    subject = native_projection_race
    request = subject.request(projection_kind)
    barrier = subject.barrier
    barrier.reply_kind = "operation_projected" if projection_kind == "result" else "operation_page"
    barrier.request_id = request.request_id
    barrier.enabled.set()
    reading = subject.pool.submit(subject.raw.operation, request, deadline=time.monotonic() + 10)
    try:
        assert barrier.entered.wait(3), "final native write did not reach its bounded barrier"
        host = subject.profiles._profiles[subject.profile_id]
        acquired = host.guard.acquire(blocking=False)
        if acquired:
            host.guard.release()
        assert not acquired, "final native projection write released its authority fence"
        denying = subject.pool.submit(subject.control.deny_automation, AutomationDenialKind.PROFILE_LOCK, timeout=5)
        assert barrier.denial_received.wait(3), "independent native denial did not reach the server"
        assert barrier.events() == ("private_entered", "denial_received")
        barrier.release.set()
        reply = reading.result(timeout=5)
        subject.assert_projection(reply)
        denied = denying.result(timeout=5)
        assert denied.profile_id == subject.profile_id and denied.access_denied
        assert barrier.denial_written.wait(3)
        assert barrier.events() == ("private_entered", "denial_received", "private_written", "denial_written")
        assert isinstance(
            subject.raw.operation(subject.request(projection_kind), deadline=time.monotonic() + 5),
            RuntimeAccessRefusal,
        )
        subject.assert_terminal_unchanged()
    finally:
        barrier.release.set()


def test_native_paged_inventory_refuses_continuation_after_global_lock(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requested = {uuid4() for _ in range(36)}
        for identity in requested:
            subject.service.request(identity, subject.proposal)
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    raw, control_raw = _connect(endpoint), _connect(endpoint)
                    client, control = (
                        RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI),
                        RuntimeFrontendClient(
                            control_raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI
                        ),
                    )
                    cleanup.callback(client.close)
                    cleanup.callback(control.close)
                    client.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    control.login_password(bytearray(PROFILE_INPUT.encode()), timeout=25)
                    contract, submitted, observed = _submit_operation(
                        raw,
                        profile_id=profile_id,
                        session_id=client.session_id,
                        definition_id=AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID,
                        payload=AutomationOperationRequest(profile_id=profile_id, request_id=uuid4()),
                    )
                    assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    schema = contract.contract.result_schema
                    assert schema is not None
                    result = OperationResultProjectionRequestV1(
                        operation_id=submitted.receipt.operation_id,
                        terminal_revision=observed.projection.revision,
                        definition_contract_digest=contract.contract.definition_contract_digest,
                        result_schema=schema,
                    )
                    document = client.read_result_document(result, timeout=30)
                    encoded = canonical_json_bytes(document)
                    assert len(encoded) > PROJECTION_PAGE_BYTES
                    inventory = (
                        OperationResultProjectionSuccessV1[AutomationInventoryProjection]
                        .model_validate_json(encoded)
                        .projection
                    )
                    assert {item.receipt.request_id for item in inventory.requests} == requested
                    first = client.operation(
                        RuntimeOperationResultPage(
                            request_id=uuid4(),
                            profile_id=profile_id,
                            session_id=client.session_id,
                            result=result,
                            page=ProjectionPageRequest(),
                        ),
                        deadline=time.monotonic() + 10,
                    )
                    assert isinstance(first, RuntimeOperationPage)
                    control.deny_automation(AutomationDenialKind.PROFILE_LOCK)
                    with pytest.raises(RuntimeFrontendRefusedError):
                        client.operation(
                            RuntimeOperationResultPage(
                                request_id=uuid4(),
                                profile_id=profile_id,
                                session_id=client.session_id,
                                result=result,
                                page=ProjectionPageRequest(
                                    offset=len(first.page.decode()), expected_digest=first.page.document_digest
                                ),
                            ),
                            deadline=time.monotonic() + 10,
                        )
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
