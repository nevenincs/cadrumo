"""One connection demultiplexes pushed retirements and correlated replies."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeRequest
from cadrumo.application.runtime.session_events import RuntimeSessionEvent
from cadrumo.application.runtime.sign_in import RuntimeSignInStatusRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind

from ..framing import VerifiedRuntimeConnection, accept_runtime_handshake
from ..frontend_client import RuntimeFrontendClient
from ..frontend_client_contracts import RuntimeFrontendRefusedError
from ..runtime_frame_io import read_document, write_document, write_session_event
from .test_frontend_access_management import _channels

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_same_connection_events_demultiplex_and_clear_idle_client() -> None:
    inbound, outbound, identity = _channels()
    connection_id, profile_id, session_id = uuid4(), uuid4(), uuid4()
    send, done, retired = Event(), Event(), Event()
    notice = RuntimeSessionEvent(
        runtime_boot_id=identity.boot_id,
        connection_id=connection_id,
        profile_id=profile_id,
        session_id=session_id,
        event=SessionRetirementKind.SIGNED_OUT,
        reason=AccessDenialCode.AUTHENTICATION_REQUIRED,
        generation_lineage=uuid4(),
        generation=2,
    )

    def serve() -> None:
        accept_runtime_handshake(outbound, identity=identity, deadline=time.monotonic() + 5)
        assert send.wait(5)
        # Both event and reply are on the same channel. The exchange lock
        # assigns all reads to either the pending request or the idle pump.
        write_session_event(outbound, notice, deadline=time.monotonic() + 5)
        request = read_document(outbound, RuntimeRequest, deadline=time.monotonic() + 5).root
        write_document(
            outbound,
            RuntimeAccessRefusal(
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
        connection = VerifiedRuntimeConnection(
            inbound,
            expected=RuntimeClientHello(
                product_version=identity.product_version, storage_identity=identity.storage_identity
            ),
            deadline=time.monotonic() + 5,
        )
        client = RuntimeFrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
        # Explicit wire fixture, not evidence of authenticated native admission.
        client._session_id = session_id
        unsubscribe = client.subscribe_session_retirement(retired.set)
        try:
            send.set()
            response = connection.sign_in_status(
                RuntimeSignInStatusRequest(request_id=uuid4(), profile_id=profile_id),
                deadline=time.monotonic() + 5,
            )
            assert isinstance(response, RuntimeAccessRefusal) and response.code is AccessDenialCode.PROFILE_LOCKED
            assert retired.wait(5)
            with pytest.raises(RuntimeFrontendRefusedError):
                _ = client.session_id
        finally:
            unsubscribe()
            done.set()
            client.close()
            serving.result(timeout=5)
            outbound.close()
