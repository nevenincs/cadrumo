"""The verified parent control pipe alone accepts the rotation wait command."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.profile_worker_support import worker_profiles
from cadrumo.application.auth.operation_definitions import PROFILE_ROTATION_OPERATION_DEFINITION_ID
from cadrumo.application.operations.models import OperationIdentity, new_operation_id
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerRequest,
    ProfileWorkerSettlement,
    ProfileWorkerSettlementRequest,
)
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import profile_operation_subject

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_control_routes_unknown_rotation_to_typed_refusal_and_operation_pipe_rejects_it(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as profiles:
        root, ((worker_identity, _), _) = profiles
        worker = ProfileWorkerProcess(worker_identity, storage_root=root)
        identity = OperationIdentity(
            operation_id=new_operation_id(),
            definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(worker_identity.binding.profile_id)),
        )
        try:
            with pytest.raises(ProfileAccessRefusedError) as refused:
                worker.settlement(identity, timeout=0.1)
            assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
            assert worker.status().identity == worker_identity

            request = ProfileWorkerSettlementRequest(
                request_id=uuid4(),
                operation_identity=identity,
                wait_seconds=0.1,
            )
            with pytest.raises(RuntimeRefusalError):
                worker._exchange(
                    ProfileWorkerRequest(request),
                    ProfileWorkerSettlement,
                    operation=True,
                    deadline=time.monotonic() + 3,
                )
        finally:
            worker.close()
            worker.settle()
