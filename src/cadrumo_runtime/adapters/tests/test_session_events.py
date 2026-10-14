"""One connection demultiplexes pushed retirements and correlated replies."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.profile_access import AccessRefusal, Request
from cadrumo_client.contracts.session_events import LifecycleNotice, SessionEvent
from cadrumo_client.contracts.sign_in import SignInStatusRequest
from cadrumo_client.transport.frame_io import read_document, write_document, write_session_event
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake

from .test_frontend_access_management import _channels

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("lifecycle", [False, True])
def test_same_connection_events_demultiplex_and_clear_idle_client(lifecycle: bool) -> None:
    inbound, outbound, identity = _channels()
    connection_id, profile_id, session_id = uuid4(), uuid4(), uuid4()
    send, done, retired = Event(), Event(), Event()
    notice = (
        LifecycleNotice(runtime_boot_id=identity.boot_id, connection_id=connection_id, notice_id=uuid4())
        if lifecycle
        else SessionEvent(
            runtime_boot_id=identity.boot_id,
            connection_id=connection_id,
            profile_id=profile_id,
            session_id=session_id,
            event=SessionRetirementKind.SIGNED_OUT,
            reason=AccessDenialCode.AUTHENTICATION_REQUIRED,
            generation_lineage=uuid4(),
            generation=2,
        )
    )

    def serve() -> None:
        accept_connection_handshake(outbound, identity=identity, deadline=time.monotonic() + 5)
        assert send.wait(5)
        # Both event and reply are on the same channel. The exchange lock
        # assigns all reads to either the pending request or the idle pump.
        write_session_event(outbound, notice, deadline=time.monotonic() + 5)
        request = read_document(outbound, Request, deadline=time.monotonic() + 5).root
        write_document(
            outbound,
            AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=identity.boot_id,
                connection_id=connection_id,
                code=AccessDenialCode.PROFILE_LOCKED,
            ),
            deadline=time.monotonic() + 5,
        )
        assert done.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        serving = pool.submit(serve)
        connection = VerifiedConnection(
            inbound,
            expected=ClientHello(
                product_version=identity.product_version,
                storage_identity=identity.storage_identity,
                lifecycle_notices="v1" if lifecycle else None,
            ),
            deadline=time.monotonic() + 5,
        )
        client = FrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
        # Explicit wire fixture, not evidence of authenticated native admission.
        client._session_id = session_id
        unsubscribe = client.subscribe_session_retirement(retired.set)
        notices: list[LifecycleNotice] = []
        unsubscribe_notice = client.subscribe_lifecycle_notices(notices.append)
        try:
            send.set()
            response = connection.sign_in_status(
                SignInStatusRequest(request_id=uuid4(), profile_id=profile_id),
                deadline=time.monotonic() + 5,
            )
            assert isinstance(response, AccessRefusal) and response.code is AccessDenialCode.PROFILE_LOCKED
            if lifecycle:
                assert notices == [notice]
                assert not retired.is_set()
                assert client.session_id == session_id
                replayed: list[LifecycleNotice] = []
                client.subscribe_lifecycle_notices(replayed.append)()
                assert replayed == [notice]
            else:
                assert retired.wait(5)
                with pytest.raises(FrontendRefusedError):
                    _ = client.session_id
        finally:
            unsubscribe()
            unsubscribe_notice()
            done.set()
            client.close()
            serving.result(timeout=5)
            outbound.close()
