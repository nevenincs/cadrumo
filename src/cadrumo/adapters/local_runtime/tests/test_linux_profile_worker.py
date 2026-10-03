"""Real Linux private worker admission through one systemd-owned profile scope."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from cadrumo.application.auth.auth_read_contracts import AuthReadRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.core.operations import OperationTerminalCondition

from ..profile_worker import ProfileWorkerProcess
from .profile_worker_support import changed, lease, worker_profiles
from .test_profile_worker import _AllowWorkerOperations

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux user-systemd worker containment"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_linux_profile_worker_admits_exact_profile_and_releases_registered_read(tmp_path: Path) -> None:
    with worker_profiles(tmp_path) as (root, subjects):
        identity, key = subjects[0]
        admitted = lease(identity)
        admitted = changed(
            admitted,
            scope=AccessScope(
                operations=frozenset({"auth.local-read"}),
                actions=admitted.scope.actions,
                disclosures=frozenset(
                    {
                        DisclosurePermission(
                            destination_id=admitted.client_id,
                            projection_id="auth.local-read.result",
                            category=DisclosureCategory.PROFILE_VALUES,
                        ),
                        DisclosurePermission(
                            destination_id=admitted.client_id,
                            projection_id="operation.observation",
                            category=DisclosureCategory.OPERATION_METADATA,
                        ),
                    }
                ),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
        )
        worker = ProfileWorkerProcess(identity, storage_root=root, authorization=_AllowWorkerOperations())
        try:
            secret = bytearray(key)
            worker.install(admitted, secret)
            assert not any(secret)
            assert worker.status().sessions == (admitted.session_id,)
            contract = worker.describe(admitted.session_id, "auth.local-read").contract
            assert contract.definition_id == "auth.local-read"
            assert contract.result_schema is not None
            request = OperationRequest(
                definition_id="auth.local-read",
                subject_ref=f"profile:{identity.binding.profile_id}",
                payload=AuthReadRequest(profile_id=identity.binding.profile_id, kind="status"),
            )
            submitted = worker.submit(admitted.session_id, request, frontend=OperationFrontendProjection.MCP)
            worker.start(admitted.session_id, submitted.receipt.operation_id)
            deadline = time.monotonic() + 30
            while True:
                observed = worker.observe(
                    admitted.session_id,
                    OperationObservationRequestV1(
                        operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=32
                    ),
                ).observation
                assert isinstance(observed, OperationObservationSuccessV1)
                projection = observed.projection
                if projection.terminal_condition is not None:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.05)
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
            result = worker.project(
                admitted.session_id,
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                frontend=OperationFrontendProjection.MCP,
            )
            assert result.document["outcome"] == "success"
            released = result.document["projection"]
            assert isinstance(released, dict)
            assert released["profile_id"] == str(identity.binding.profile_id)
        finally:
            worker.close()
