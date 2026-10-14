"""Installed admission retains failed connection cleanup without masking refusal."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessScope
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo_client.contracts.contracts import ClientHello, ServerHello
from cadrumo_client.transport import credentials
from cadrumo_client.transport.credentials import open_installed_credential_client
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.adapters.tests.test_enrollment_framing import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _CloseChannel(MemoryChannel):
    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0
        self.fail_once = True
        self.closed = False

    @override
    def close(self) -> None:
        self.close_calls += 1
        if self.fail_once and self.close_calls == 1:
            raise OSError("synthetic channel close failure")
        super().close()
        self.closed = True


@pytest.fixture
def connection() -> Iterator[tuple[FrontendClient, _CloseChannel]]:
    channel, peer = _CloseChannel(), MemoryChannel()
    channel.pair(peer)
    expected = ClientHello(product_version="test", storage_identity="a" * 64)
    deadline = time.monotonic() + 5
    write_document(
        peer,
        ServerHello(
            product_version=expected.product_version,
            storage_identity=expected.storage_identity,
            boot_id=uuid4(),
        ),
        deadline=deadline,
    )
    verified = VerifiedConnection(channel, expected=expected, deadline=deadline)
    client = FrontendClient(verified, profile_id=uuid4(), frontend=OperationFrontendProjection.EXTERNAL_CLIENT)
    try:
        yield client, channel
    finally:
        try:
            client.close()
        except OSError:
            client.close()
        peer.close()


def _admission_ports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    client: FrontendClient,
    authenticate: Callable[[], None],
) -> UUID:
    reference = uuid4()

    async def open_transport(
        *, profile_id: UUID, frontend: OperationFrontendProjection, timeout: float, scope: AccessScope | None
    ) -> FrontendClient:
        assert profile_id == client.profile_id
        assert frontend is client.frontend
        assert scope is None
        assert timeout > 0
        return client

    def authenticate_reference(
        received: FrontendClient,
        *,
        root: Path,
        credential_reference: UUID,
        secrets_store: AutomationSecretStore | None,
        deadline: float,
    ) -> None:
        assert received is client
        assert root == tmp_path.resolve(strict=True)
        assert credential_reference == reference
        assert secrets_store is None
        assert deadline > time.monotonic()
        authenticate()

    monkeypatch.setattr(credentials, "effective_storage_root", lambda: tmp_path)
    monkeypatch.setattr(credentials, "open_installed_client", open_transport)
    monkeypatch.setattr(credentials, "_authenticate_reference", authenticate_reference)
    return reference


@pytest.mark.asyncio
async def test_admission_refusal_preserves_identity_and_retains_failed_native_close_for_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    connection: tuple[FrontendClient, _CloseChannel],
) -> None:
    client, channel = connection
    refusal = AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
    connected: list[FrontendClient] = []

    def refuse() -> None:
        assert connected == [client]
        raise refusal

    reference = _admission_ports(monkeypatch, tmp_path, client, refuse)
    with pytest.raises(AutomationCustodyError) as caught:
        await open_installed_credential_client(
            profile_id=client.profile_id,
            credential_reference=reference,
            frontend=client.frontend,
            on_connected=connected.append,
        )
    assert caught.value is refusal
    cleanup = refusal.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert channel.close_calls == 1 and not channel.closed
    await cleanup.retry_cleanup()
    assert channel.closed and channel.close_calls == 2
    client.close()
    assert channel.close_calls == 2


@pytest.mark.asyncio
async def test_repeated_admission_cancellation_retains_failed_cleanup_owner_for_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    connection: tuple[FrontendClient, _CloseChannel],
) -> None:
    async def scenario() -> None:
        client, channel = connection
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = Event()

        def blocked_authentication() -> None:
            loop.call_soon_threadsafe(started.set)
            if not release.wait(timeout=5):
                raise TimeoutError("controlled admission was not released")

        reference = _admission_ports(monkeypatch, tmp_path, client, blocked_authentication)
        admission = asyncio.create_task(
            open_installed_credential_client(
                profile_id=client.profile_id, credential_reference=reference, frontend=client.frontend
            )
        )
        try:
            await started.wait()
            for _ in range(2):
                admission.cancel()
                checkpoint = asyncio.Event()
                loop.call_soon(checkpoint.set)
                await checkpoint.wait()
                assert not admission.done()
                assert channel.close_calls == 0
            release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await admission
            cleanup = caught.value.__dict__.get("cleanup_error")
            assert isinstance(cleanup, AsyncResourceCleanupError)
            assert channel.close_calls == 1 and not channel.closed
            await cleanup.retry_cleanup()
            assert channel.closed and channel.close_calls == 2
            client.close()
            assert channel.close_calls == 2
        finally:
            release.set()
            if not admission.done():
                with suppress(asyncio.CancelledError):
                    await admission

    await asyncio.wait_for(scenario(), timeout=10)


@pytest.mark.asyncio
async def test_successful_admission_transfers_connection_cleanup_to_caller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    connection: tuple[FrontendClient, _CloseChannel],
) -> None:
    client, channel = connection
    channel.fail_once = False
    authenticated = Event()
    reference = _admission_ports(monkeypatch, tmp_path, client, authenticated.set)
    admitted = await open_installed_credential_client(
        profile_id=client.profile_id, credential_reference=reference, frontend=client.frontend
    )
    assert admitted is client
    assert authenticated.is_set()
    assert channel.close_calls == 0 and not channel.closed
    admitted.close()
    assert channel.close_calls == 1 and channel.closed
