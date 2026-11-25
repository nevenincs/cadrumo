"""A second sign-in on a warm profile worker never waits for its operation registry.

The worker composes the registry, its handlers and the tax authority for the
first operation a session asks for. A second person signing in to the same
worker meanwhile is answered within the worker's own exchange budgets: it once
queued behind that composition on the worker's control channel and its binding
timed out after the 10 s control budget. The real transport enforces those
budgets, so a regression surfaces as a refused sign-in, not as a wall-clock
threshold this test would have to guess.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo_client.contracts.operation_access import OperationContract, OperationContractReply
from cadrumo_client.contracts.profile_access import ProfileStatus

from .served_profile_runtime import serving_enrolled_profile
from .served_runtime import connect_verified
from .test_profile_connections import login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows workers"),
    pytest.mark.usefixtures("authority_operation"),
]


@pytest.mark.parametrize("composing", [False, True], ids=["idle", "composing"])
def test_a_second_sign_in_is_answered_while_the_first_operation_composes(tmp_path: Path, composing: bool) -> None:
    with serving_enrolled_profile(tmp_path, workers=2) as profile:
        endpoint, profile_id = profile.endpoint, profile.profile_id
        served = profile.served
        first, second = connect_verified(endpoint), connect_verified(endpoint)
        try:
            admitted = login(first, profile_id, "password", PROFILE_INPUT.encode())
            assert isinstance(admitted, ProfileStatus)
            session = admitted.status.session_id
            assert session is not None
            # The first session's first operation composes the registry,
            # alongside the second sign-in or after it.
            request = OperationContract(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session,
                definition_id="user-profile.field-mutation",
            )
            contract = (
                served.pool.submit(first.operation, request, deadline=time.monotonic() + 75) if composing else None
            )
            started = time.monotonic()
            again = login(second, profile_id, "password", PROFILE_INPUT.encode())
            elapsed = time.monotonic() - started
            if contract is None:
                contract = served.pool.submit(first.operation, request, deadline=time.monotonic() + 75)
            print("second_sign_in_seconds", elapsed, "composition_done", contract.done(), flush=True)

            assert isinstance(again, ProfileStatus)
            assert again.status.denial is None
            assert again.status.session_id not in {None, session}
            assert isinstance(contract.result(timeout=90), OperationContractReply)
        finally:
            first.close()
            second.close()
