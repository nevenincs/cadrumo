"""Closing an exact connection wakes a held reply without acquiring its exchange slot."""

from __future__ import annotations

import time
from threading import Event, Thread
from uuid import uuid4

import pytest

from ...contracts.contracts import ClientHello, RefusalCode, RefusalError, ServerHello
from ...contracts.profile_access import SessionRequest
from ..frame_io import DOCUMENT_FRAME_KIND, read_frame_payload, write_document
from ..framing import VerifiedConnection
from .memory_channel import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_close_wakes_a_held_reply_and_returns_before_the_peer_replies() -> None:
    server, client = MemoryChannel(), MemoryChannel()
    server.pair(client)
    write_document(
        server,
        ServerHello(product_version="close-test", storage_identity="a" * 64, boot_id=uuid4()),
        deadline=time.monotonic() + 5,
    )
    connection = VerifiedConnection(
        client,
        expected=ClientHello(product_version="close-test", storage_identity="a" * 64),
        deadline=time.monotonic() + 5,
    )
    read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
    errors: list[RefusalError] = []
    replies: list[object] = []
    closed = Event()

    def read() -> None:
        try:
            replies.append(
                connection.session(
                    SessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
                    deadline=time.monotonic() + 120,
                )
            )
        except RefusalError as error:
            errors.append(error)

    def close() -> None:
        connection.close()
        closed.set()

    reader = Thread(target=read)
    reader.start()
    closer = Thread(target=close)
    try:
        read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
        closer.start()
        assert closed.wait(2), "close must not queue behind the held request/reply slot"
        reader.join(2)
        assert not reader.is_alive()
        assert replies == []
        assert [error.reason for error in errors] == [RefusalCode.CONNECTION_CLOSED]
        assert connection.closed
        connection.close()
    finally:
        server.close()
        reader.join(5)
        if closer.ident is not None:
            closer.join(5)
        connection.close()
