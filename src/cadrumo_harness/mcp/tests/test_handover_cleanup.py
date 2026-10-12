"""Temporary MCP clients remain owned until their retirement succeeds."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from threading import Event
from typing import cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.tests.test_authentication_handover import _Client

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _CloseClient(_Client):
    def __init__(self, profile_id: UUID, *, fail_once: bool = False, fail_status: bool = False) -> None:
        super().__init__(profile_id, fail_status=fail_status)
        self.fail_once = fail_once
        self.close_calls = 0

    @override
    def close(self) -> None:
        self.close_calls += 1
        if self.fail_once and self.close_calls == 1:
            raise OSError("synthetic close failure")
        super().close()


def _adapter(client: _CloseClient) -> RuntimeMcpAdapter:
    return RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))


def _admit(monkeypatch: pytest.MonkeyPatch, candidate: _CloseClient) -> None:
    async def admit(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        assert profile_id == candidate.profile_id
        assert frontend is OperationFrontendProjection.MCP
        assert isinstance(credential_reference, UUID)
        return cast(RuntimeFrontendClient, candidate)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", admit)


@pytest.mark.asyncio
async def test_teardown_preserves_body_error_and_retains_failed_client_for_retry() -> None:
    client = _CloseClient(uuid4(), fail_once=True)
    adapter = _adapter(client)
    body_error = ValueError("synthetic server body failure")
    try:
        with pytest.raises(ValueError) as caught:
            try:
                raise body_error
            finally:
                await adapter.close()
        assert caught.value is body_error
        cleanup_error = body_error.__dict__.get("async_cleanup_error")
        assert isinstance(cleanup_error, AsyncResourceCleanupError)
        assert client.close_calls == 1 and not client.closed
        await cleanup_error.retry_cleanup()
        assert client.closed and client.close_calls == 2
        await adapter.close()
        assert client.close_calls == 2
    finally:
        await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["refusal", "cancellation", "aliased_cancellation"])
async def test_opener_failure_transfers_retained_cleanup_to_adapter(
    monkeypatch: pytest.MonkeyPatch, failure_kind: str
) -> None:
    class FailedAdmissionOwner:
        def __init__(self) -> None:
            self.close_calls = 0
            self.closed = False

        async def close(self) -> None:
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("synthetic helper-owned close failure")
            self.closed = True

    original = _CloseClient(uuid4())
    failed_owner = FailedAdmissionOwner()
    reference = uuid4()
    refusal: BaseException = (
        asyncio.CancelledError("synthetic admission cancellation")
        if failure_kind != "refusal"
        else AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    )

    async def refuse_admission(
        *, profile_id: UUID, frontend: OperationFrontendProjection, credential_reference: UUID
    ) -> RuntimeFrontendClient:
        assert profile_id == original.profile_id
        assert credential_reference == reference
        assert frontend is OperationFrontendProjection.MCP
        try:
            await close_async_resources(failed_owner, task_name="test-helper-admission-close", primary_error=refusal)
        finally:
            field = "async_cleanup_error" if failure_kind == "refusal" else "cleanup_error"
            failure = refusal.__dict__.get(field)
            assert isinstance(failure, AsyncResourceCleanupError)
            if failure_kind == "aliased_cancellation":
                refusal.__dict__["async_cleanup_error"] = failure
        raise refusal

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", refuse_admission)
    adapter = _adapter(original)
    try:
        if failure_kind == "refusal":
            await adapter.bootstrap_reference(reference)
            denial = adapter._admission_denial
            assert denial is not None and denial.code == AutomationCustodyCode.UNAVAILABLE.value
        else:
            with pytest.raises(asyncio.CancelledError) as caught:
                await adapter.bootstrap_reference(reference)
            assert caught.value is refusal
        assert adapter.client is original
        assert not original.closed
        assert failed_owner.close_calls == 1 and not failed_owner.closed
        await adapter.close()
        assert failed_owner.closed and original.closed
        assert failed_owner.close_calls == 2
        assert original.close_calls == 1
        await adapter.close()
        assert failed_owner.close_calls == 2
        assert original.close_calls == 1
    finally:
        await adapter.close()
        if not failed_owner.closed:
            await close_async_resources(failed_owner, task_name="test-helper-owner-release", primary_error=None)


@pytest.mark.asyncio
async def test_reauthentication_keeps_candidate_and_retries_failed_predecessor_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _CloseClient(uuid4(), fail_once=True)
    candidate = _CloseClient(original.profile_id)
    _admit(monkeypatch, candidate)
    adapter = _adapter(original)
    try:
        await adapter.bootstrap_reference(uuid4())
        denial = adapter._admission_denial
        assert denial is not None and denial.code == "runtime_unavailable"
        assert adapter.client is candidate
        assert not original.closed and not candidate.closed
        await adapter.close()
        assert original.closed and candidate.closed
        assert original.close_calls == 2
        assert candidate.close_calls == 1
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_candidate_denial_survives_close_failure_and_candidate_is_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _CloseClient(uuid4())
    candidate = _CloseClient(original.profile_id, fail_once=True, fail_status=True)
    _admit(monkeypatch, candidate)
    adapter = _adapter(original)
    try:
        await adapter.bootstrap_reference(uuid4())
        denial = adapter._admission_denial
        assert denial is not None and denial.code == "session_expired"
        assert adapter.client is original
        assert not original.closed and not candidate.closed
        await adapter.close()
        assert original.closed and candidate.closed
        assert original.close_calls == 1
        assert candidate.close_calls == 2
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_temporary_close_without_closing_it_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = Event()
        loop = asyncio.get_running_loop()

        class BlockedCandidate(_CloseClient):
            @override
            def close(self) -> None:
                loop.call_soon_threadsafe(started.set)
                if not release.wait(timeout=5):
                    raise TimeoutError("temporary close was not released")
                super().close()

        original = _CloseClient(uuid4())
        candidate = BlockedCandidate(original.profile_id, fail_status=True)
        _admit(monkeypatch, candidate)
        adapter = _adapter(original)
        calling = asyncio.create_task(adapter.bootstrap_reference(uuid4()))
        try:
            await started.wait()
            for _ in range(2):
                calling.cancel()
                checkpoint = asyncio.Event()
                loop.call_soon(checkpoint.set)
                await checkpoint.wait()
                assert not calling.done()
                assert not candidate.closed
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await calling
            assert candidate.closed
            assert candidate.close_calls == 1
            assert adapter.client is original
            await adapter.close()
            assert original.closed
            assert original.close_calls == candidate.close_calls == 1
        finally:
            release.set()
            if not calling.done():
                with suppress(asyncio.CancelledError):
                    await calling
            await adapter.close()

    await asyncio.wait_for(scenario(), timeout=10)
