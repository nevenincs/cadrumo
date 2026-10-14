"""Verified enrollment framing keeps every protected exchange on one channel."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Condition
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import ClientHello, Peer, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.enrollment_access import (
    EnrollmentClientReply,
    EnrollmentCredentialBinding,
    EnrollmentDelivery,
    EnrollmentIdle,
    EnrollmentInspect,
    EnrollmentPoll,
    EnrollmentPrepare,
    EnrollmentPrepared,
    EnrollmentRecorded,
    EnrollmentSubmit,
)
from cadrumo_client.contracts.profile_access import SecretReady
from cadrumo_client.transport.frame_io import read_document, read_secret, write_document, write_secret
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class MemoryChannel:
    """Explicit bounded byte-channel port; document and secret framing stay real."""

    def __init__(self) -> None:
        self._condition = Condition()
        self._data = bytearray()
        self._closed = False
        self._other: MemoryChannel | None = None
        self.writes: list[bytes] = []
        self.peer = Peer(os_owner_id="synthetic-owner", process_id=1)

    def pair(self, other: MemoryChannel) -> None:
        self._other = other
        other._other = self

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self._condition:
            while len(self._data) < count:
                if self._closed or (self._other is not None and self._other._closed):
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
                self._condition.wait(remaining)
            result = bytes(self._data[:count])
            del self._data[:count]
            return result

    def read_ready(self) -> bool:
        with self._condition:
            return bool(self._data) or self._closed or (self._other is not None and self._other._closed)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        other = self._other
        if other is None or time.monotonic() >= deadline:
            raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
        with other._condition:
            if self._closed or other._closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            self.writes.append(bytes(payload))
            other._data.extend(payload)
            other._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._other is not None:
            with self._other._condition:
                self._other._condition.notify_all()


def _channels() -> tuple[MemoryChannel, MemoryChannel, ServerHello]:
    client, server = MemoryChannel(), MemoryChannel()
    client.pair(server)
    identity = ServerHello(product_version="enrollment-test", storage_identity="a" * 64, boot_id=uuid4())
    return client, server, identity


def _client(channel: MemoryChannel, identity: ServerHello) -> VerifiedConnection:
    return VerifiedConnection(
        channel,
        expected=ClientHello(product_version=identity.product_version, storage_identity=identity.storage_identity),
        deadline=time.monotonic() + 5,
    )


def _binding() -> ProfileAccessBinding:
    return ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )


def test_prepare_submit_and_inspect_keep_proposal_only_in_secret_frame() -> None:
    client_channel, server_channel, identity = _channels()
    binding = _binding()
    enrollment_request_id = uuid4()
    connection_id = uuid4()
    receipt = AutomationReceiptProjection(
        request_id=enrollment_request_id,
        profile_id=binding.profile_id,
        stage=EnrollmentStage.REQUESTED,
        review_digest="a" * 64,
        grant_id=uuid4(),
        key_id=None,
        credential_reference=None,
    )
    prepare = EnrollmentPrepare(
        request_id=uuid4(), profile_id=binding.profile_id, frontend=OperationFrontendProjection.CLI
    )
    submit = EnrollmentSubmit(
        request_id=uuid4(), profile_id=binding.profile_id, enrollment_request_id=enrollment_request_id
    )
    inspect = EnrollmentInspect(
        request_id=uuid4(), profile_id=binding.profile_id, enrollment_request_id=enrollment_request_id
    )
    proposal = bytearray(b"synthetic-private-proposal")

    def serve() -> None:
        try:
            accept_connection_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            first = read_document(server_channel, EnrollmentPrepare, deadline=time.monotonic() + 5)
            assert first == prepare
            write_document(
                server_channel,
                EnrollmentPrepared(
                    request_id=first.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    enrollment_request_id=enrollment_request_id,
                    client_id=uuid4(),
                    destination_id=uuid4(),
                    profile_binding=binding,
                    expires_at=now() + timedelta(minutes=1),
                ),
                deadline=time.monotonic() + 5,
            )
            second = read_document(server_channel, EnrollmentSubmit, deadline=time.monotonic() + 5)
            assert second == submit
            write_document(
                server_channel,
                SecretReady(
                    request_id=second.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
                ),
                deadline=time.monotonic() + 5,
            )
            with read_secret(server_channel, deadline=time.monotonic() + 5) as received:
                assert received == b"synthetic-private-proposal"
            write_document(
                server_channel,
                EnrollmentRecorded(
                    request_id=second.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    receipt=receipt,
                ),
                deadline=time.monotonic() + 5,
            )
            third = read_document(server_channel, EnrollmentInspect, deadline=time.monotonic() + 5)
            assert third == inspect
            write_document(
                server_channel,
                EnrollmentRecorded(
                    request_id=third.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    receipt=receipt,
                ),
                deadline=time.monotonic() + 5,
            )
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        try:
            prepared = connection.enrollment_prepare(prepare, deadline=time.monotonic() + 5)
            assert isinstance(prepared, EnrollmentPrepared)
            assert connection.connection_id == prepared.connection_id
            recorded = connection.enrollment_submit(submit, proposal, deadline=time.monotonic() + 5)
            assert isinstance(recorded, EnrollmentRecorded) and recorded.receipt == receipt
            assert connection.enrollment_inspect(inspect, deadline=time.monotonic() + 5) == recorded.model_copy(
                update={"request_id": inspect.request_id}
            )
            assert not any(proposal)
            assert all(
                b"synthetic-private-proposal" not in frame for frame in client_channel.writes if frame[:1] == b"J"
            )
            serving.result(timeout=5)
        finally:
            connection.close()


def test_poll_stores_candidate_then_reads_fresh_possession_over_secret_frame() -> None:
    client_channel, server_channel, identity = _channels()
    binding = _binding()
    connection_id = uuid4()
    credential = EnrollmentCredentialBinding(
        profile_binding=binding,
        client_id=uuid4(),
        destination_id=uuid4(),
        credential_reference=uuid4(),
        grant_id=uuid4(),
        key_id=uuid4(),
        review_digest="a" * 64,
    )
    polls = tuple(
        EnrollmentPoll(request_id=uuid4(), profile_id=binding.profile_id, enrollment_request_id=uuid4())
        for _ in range(2)
    )
    candidate = bytearray(b"synthetic-candidate")
    observed: list[str] = []

    def serve() -> None:
        try:
            accept_connection_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            actions: tuple[Literal["store", "possession"], ...] = ("store", "possession")
            for poll, action in zip(polls, actions, strict=True):
                received = read_document(server_channel, EnrollmentPoll, deadline=time.monotonic() + 5)
                assert received == poll
                command_id = uuid4()
                write_document(
                    server_channel,
                    EnrollmentDelivery(
                        request_id=poll.request_id,
                        runtime_boot_id=identity.boot_id,
                        connection_id=connection_id,
                        command_id=command_id,
                        action=action,
                        credential=credential,
                    ),
                    deadline=time.monotonic() + 5,
                )
                if action == "store":
                    write_secret(server_channel, candidate, deadline=time.monotonic() + 5)
                answer = read_document(server_channel, EnrollmentClientReply, deadline=time.monotonic() + 5)
                assert answer.command_id == command_id
                assert answer.outcome == ("stored" if action == "store" else "present")
                if action == "possession":
                    with read_secret(server_channel, deadline=time.monotonic() + 5) as proof:
                        assert proof == b"synthetic-candidate"
                write_document(
                    server_channel,
                    EnrollmentIdle(
                        request_id=poll.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
                    ),
                    deadline=time.monotonic() + 5,
                )
        finally:
            server_channel.close()

    def store(expected: EnrollmentCredentialBinding, secret: SecretBytes) -> None:
        assert expected == credential
        assert secret.get_secret_value() == b"synthetic-candidate"
        observed.append("stored")

    def possession(expected: EnrollmentCredentialBinding) -> SecretBytes | None:
        assert expected == credential
        assert observed == ["stored"]
        observed.append("fresh-read")
        return SecretBytes(b"synthetic-candidate")

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        try:
            for poll in polls:
                result = connection.enrollment_poll(
                    poll, store=store, possession=possession, deadline=time.monotonic() + 5
                )
                assert isinstance(result, EnrollmentDelivery)
            assert observed == ["stored", "fresh-read"]
            assert not any(candidate)
            for frame in (*client_channel.writes, *server_channel.writes):
                if frame[:1] == b"J":
                    assert b"synthetic-candidate" not in frame
            serving.result(timeout=5)
        finally:
            connection.close()


def test_poll_refusal_is_typed_and_wrong_reply_correlation_closes_connection() -> None:
    client_channel, server_channel, identity = _channels()
    binding = _binding()
    connection_id = uuid4()
    credential = EnrollmentCredentialBinding(
        profile_binding=binding,
        client_id=uuid4(),
        destination_id=uuid4(),
        credential_reference=uuid4(),
        grant_id=uuid4(),
        key_id=uuid4(),
        review_digest="a" * 64,
    )
    first = EnrollmentPoll(request_id=uuid4(), profile_id=binding.profile_id, enrollment_request_id=uuid4())
    second = EnrollmentPoll(request_id=uuid4(), profile_id=binding.profile_id, enrollment_request_id=uuid4())
    candidate = bytearray(b"synthetic-refused-candidate")
    called: list[str] = []

    def store(expected: EnrollmentCredentialBinding, secret: SecretBytes) -> None:
        assert expected == credential and secret.get_secret_value() == b"synthetic-refused-candidate"
        called.append("store")
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)

    def possession(expected: EnrollmentCredentialBinding) -> SecretBytes | None:
        called.append("possession")
        return None

    def serve() -> None:
        try:
            accept_connection_handshake(server_channel, identity=identity, deadline=time.monotonic() + 5)
            assert read_document(server_channel, EnrollmentPoll, deadline=time.monotonic() + 5) == first
            command_id = uuid4()
            write_document(
                server_channel,
                EnrollmentDelivery(
                    request_id=first.request_id,
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    command_id=command_id,
                    action="store",
                    credential=credential,
                ),
                deadline=time.monotonic() + 5,
            )
            write_secret(server_channel, candidate, deadline=time.monotonic() + 5)
            answer = read_document(server_channel, EnrollmentClientReply, deadline=time.monotonic() + 5)
            assert answer.command_id == command_id
            assert answer.outcome == "refused" and answer.code is AutomationCustodyCode.CONFLICT
            write_document(
                server_channel,
                EnrollmentIdle(
                    request_id=first.request_id, runtime_boot_id=identity.boot_id, connection_id=connection_id
                ),
                deadline=time.monotonic() + 5,
            )
            assert read_document(server_channel, EnrollmentPoll, deadline=time.monotonic() + 5) == second
            write_document(
                server_channel,
                EnrollmentDelivery(
                    request_id=uuid4(),
                    runtime_boot_id=identity.boot_id,
                    connection_id=connection_id,
                    command_id=uuid4(),
                    action="possession",
                    credential=credential,
                ),
                deadline=time.monotonic() + 5,
            )
            with pytest.raises(RefusalError) as closed:
                read_document(server_channel, EnrollmentClientReply, deadline=time.monotonic() + 5)
            assert closed.value.reason is RefusalCode.CONNECTION_CLOSED
        finally:
            server_channel.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = _client(client_channel, identity)
        try:
            result = connection.enrollment_poll(
                first, store=store, possession=possession, deadline=time.monotonic() + 5
            )
            assert isinstance(result, EnrollmentDelivery)
            assert called == ["store"] and not any(candidate)
            with pytest.raises(RefusalError) as mismatch:
                connection.enrollment_poll(second, store=store, possession=possession, deadline=time.monotonic() + 5)
            assert mismatch.value.reason is RefusalCode.INVALID_FRAME
            assert called == ["store"]
            assert all(
                b"synthetic-refused-candidate" not in frame for frame in client_channel.writes if frame[:1] == b"J"
            )
            serving.result(timeout=5)
        finally:
            connection.close()
