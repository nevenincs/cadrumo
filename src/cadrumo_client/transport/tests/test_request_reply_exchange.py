"""A single-reply exchange admits only the accepted reply types for its own profile, and closes on anything else."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Thread
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.core.operations import OperationFrontendProjection

from ...contracts.access_management import ProfileRecoveryPrepare, ProfileRecoveryPrepared
from ...contracts.access_refusals import AccessDenialCode
from ...contracts.bootstrap import PasswordResetPrepare, PasswordResetPrepared
from ...contracts.contracts import ClientHello, RefusalCode, RefusalError, ServerHello
from ...contracts.profile_access import AccessRefusal
from ...contracts.sign_in import SignInPresence, SignInStatus, SignInStatusReply, SignInStatusRequest
from ..frame_io import DOCUMENT_FRAME_KIND, read_frame_payload, write_document
from ..framing import VerifiedConnection
from .memory_channel import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PROFILE = uuid4()
_OTHER_PROFILE = uuid4()
_DIGEST = "sha256:" + "a" * 64


def _exchange(
    call: Callable[[VerifiedConnection], object],
    reply: Callable[[UUID, UUID], BaseModel],
) -> tuple[object, VerifiedConnection]:
    """Run ``call`` against a connection whose peer answers its one request with ``reply(boot, connection)``."""
    boot_id = uuid4()
    server, client = MemoryChannel(), MemoryChannel()
    server.pair(client)
    write_document(
        server,
        ServerHello(product_version="reply-test", storage_identity="a" * 64, boot_id=boot_id),
        deadline=time.monotonic() + 5,
    )
    connection = VerifiedConnection(
        client,
        expected=ClientHello(product_version="reply-test", storage_identity="a" * 64),
        deadline=time.monotonic() + 5,
    )
    read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
    outcomes: list[object] = []

    def run() -> None:
        try:
            outcomes.append(call(connection))
        except RefusalError as error:
            outcomes.append(error)

    thread = Thread(target=run)
    thread.start()
    try:
        read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
        write_document(server, reply(boot_id, uuid4()), deadline=time.monotonic() + 5)
    finally:
        thread.join(5)
        server.close()
    assert not thread.is_alive()
    return outcomes[0], connection


def _sign_in(request_id: UUID, profile_id: UUID) -> Callable[[UUID, UUID], BaseModel]:
    return lambda boot, connection: SignInStatusReply(
        request_id=request_id,
        runtime_boot_id=boot,
        connection_id=connection,
        profile_id=profile_id,
        status=SignInStatus(presence=SignInPresence.ABSENT),
    )


def _recovery(request_id: UUID, profile_id: UUID) -> Callable[[UUID, UUID], BaseModel]:
    return lambda boot, connection: ProfileRecoveryPrepared(
        request_id=request_id,
        runtime_boot_id=boot,
        connection_id=connection,
        profile_id=profile_id,
        lock_generation=1,
        globally_locked=False,
    )


def _reset(request_id: UUID, profile_id: UUID) -> Callable[[UUID, UUID], BaseModel]:
    return lambda boot, connection: PasswordResetPrepared(
        request_id=request_id,
        runtime_boot_id=boot,
        connection_id=connection,
        profile_id=profile_id,
        envelope_digest=_DIGEST,
    )


def _sign_in_call(request: SignInStatusRequest) -> Callable[[VerifiedConnection], object]:
    return lambda connection: connection.sign_in_status(request, deadline=time.monotonic() + 5)


def _recovery_call(request: ProfileRecoveryPrepare) -> Callable[[VerifiedConnection], object]:
    return lambda connection: connection.recovery_prepare(request, deadline=time.monotonic() + 5)


def _reset_call(request: PasswordResetPrepare) -> Callable[[VerifiedConnection], object]:
    return lambda connection: connection.password_reset_prepare(request, deadline=time.monotonic() + 5)


@dataclass(frozen=True)
class _Case:
    """One single-reply exchange: its call, and the replies a peer could give it."""

    request_id: UUID
    call: Callable[[VerifiedConnection], object]
    own: Callable[[UUID, UUID], BaseModel]
    other_profile: Callable[[UUID, UUID], BaseModel]
    stray_type: Callable[[UUID, UUID], BaseModel]
    reply_type: type[BaseModel]


def _cases() -> list[_Case]:
    sign_in = SignInStatusRequest(request_id=uuid4(), profile_id=_PROFILE)
    recovery = ProfileRecoveryPrepare(request_id=uuid4(), profile_id=_PROFILE, frontend=OperationFrontendProjection.CLI)
    reset = PasswordResetPrepare(request_id=uuid4(), profile_id=_PROFILE, frontend=OperationFrontendProjection.CLI)
    return [
        _Case(
            sign_in.request_id,
            lambda connection: connection.sign_in_status(sign_in, deadline=time.monotonic() + 5),
            _sign_in(sign_in.request_id, _PROFILE),
            _sign_in(sign_in.request_id, _OTHER_PROFILE),
            _recovery(sign_in.request_id, _PROFILE),
            SignInStatusReply,
        ),
        _Case(
            recovery.request_id,
            lambda connection: connection.recovery_prepare(recovery, deadline=time.monotonic() + 5),
            _recovery(recovery.request_id, _PROFILE),
            _recovery(recovery.request_id, _OTHER_PROFILE),
            _sign_in(recovery.request_id, _PROFILE),
            ProfileRecoveryPrepared,
        ),
        _Case(
            reset.request_id,
            lambda connection: connection.password_reset_prepare(reset, deadline=time.monotonic() + 5),
            _reset(reset.request_id, _PROFILE),
            _reset(reset.request_id, _OTHER_PROFILE),
            _sign_in(reset.request_id, _PROFILE),
            PasswordResetPrepared,
        ),
    ]


@pytest.mark.parametrize("index", range(3))
def test_a_reply_for_the_requested_profile_is_returned_and_leaves_the_connection_open(index: int) -> None:
    case = _cases()[index]

    outcome, connection = _exchange(case.call, case.own)

    assert isinstance(outcome, case.reply_type)
    assert not connection.closed
    connection.close()


@pytest.mark.parametrize("index", range(3))
def test_a_reply_for_another_profile_is_an_invalid_frame_that_closes_the_connection(index: int) -> None:
    case = _cases()[index]

    outcome, connection = _exchange(case.call, case.other_profile)

    assert isinstance(outcome, RefusalError)
    assert outcome.reason is RefusalCode.INVALID_FRAME
    assert connection.closed


@pytest.mark.parametrize("index", range(3))
def test_a_reply_of_an_unaccepted_type_is_an_invalid_frame_that_closes_the_connection(index: int) -> None:
    case = _cases()[index]

    outcome, connection = _exchange(case.call, case.stray_type)

    assert isinstance(outcome, RefusalError)
    assert outcome.reason is RefusalCode.INVALID_FRAME
    assert connection.closed


@pytest.mark.parametrize("index", range(3))
def test_a_refusal_is_returned_without_closing_the_connection(index: int) -> None:
    case = _cases()[index]
    outcome, connection = _exchange(
        case.call,
        lambda boot, connection_id: AccessRefusal(
            request_id=case.request_id,
            runtime_boot_id=boot,
            connection_id=connection_id,
            code=AccessDenialCode.OPERATION_UNAVAILABLE,
        ),
    )

    assert isinstance(outcome, AccessRefusal)
    assert not connection.closed
    connection.close()
