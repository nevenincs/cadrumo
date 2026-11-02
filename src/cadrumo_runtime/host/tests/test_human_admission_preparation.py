"""Cold human admission prepares contracts before publishing a usable session."""

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


@pytest.mark.parametrize("_attempt", range(3))
def test_cold_and_shared_human_admission_publish_ready_contracts(tmp_path: Path, _attempt: int) -> None:
    with serving_enrolled_profile(tmp_path) as profile:
        endpoint, profile_id = profile.endpoint, profile.profile_id
        first, second = connect_verified(endpoint), connect_verified(endpoint)
        try:
            sessions = []
            for client in (first, second):
                started = time.monotonic()
                admitted = login(client, profile_id, "password", PROFILE_INPUT.encode())
                print("human_admission_seconds", time.monotonic() - started, flush=True)
                assert isinstance(admitted, ProfileStatus)
                assert admitted.status.denial is None
                session = admitted.status.session_id
                assert session is not None
                sessions.append(session)
                contract = client.operation(
                    OperationContract(
                        request_id=uuid4(),
                        profile_id=profile_id,
                        session_id=session,
                        definition_id="user-profile.field-mutation",
                    ),
                    deadline=time.monotonic() + 10,
                )
                assert isinstance(contract, OperationContractReply)
            assert sessions[0] != sessions[1]
        finally:
            first.close()
            second.close()
