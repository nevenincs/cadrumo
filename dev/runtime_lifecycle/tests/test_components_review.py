"""Real native PLAN and runtime response authority; no component is downloaded.

The native role image is supplied through CADRUMO_DEVELOPMENT_ROLE_IMAGE and
staged by the existing package fixture. Native custody and installed-image
verification use the service-runtime fixture's explicit OS test ports.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_SETUP_DEFINITION_ID,
    ProvisionMutationRequest,
    ProvisionResult,
    ProvisionReviewProjection,
)
from cadrumo.application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResponseRejectRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from cadrumo.core.time.clock import now
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.operation_access import OperationReviewClaim, OperationReviewClaimed
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_changes import AsyncOperationChanges
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.agent_key_reads import tool_document
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.host.tests.test_service_records import ServiceRecordRuntime, service_record_runtime

__all__ = ["components_role_fixture", "counting_proxy_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


def _frontend(runtime: ServiceRecordRuntime, projection: OperationFrontendProjection) -> FrontendClient:
    connection = VerifiedConnection(
        runtime.endpoint.connect(timeout=3),
        expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    return FrontendClient(
        connection,
        profile_id=runtime.profile_id,
        frontend=projection,
        scope=AccessScope(
            operations=frozenset({COMPONENTS_SETUP_DEFINITION_ID}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )
        if projection is OperationFrontendProjection.EXTERNAL_CLIENT
        else None,
    )


async def _waiting(
    frontend: FrontendClient,
    read: Callable[[], Awaitable[OperationPublicProjectionV1]],
    *,
    target: OperationLifecycle = OperationLifecycle.WAITING_FOR_INTERACTION,
) -> OperationPublicProjectionV1:
    with AsyncOperationChanges(frontend) as changes:
        async with asyncio.timeout(120):
            while True:
                changes.arm()
                projection = await read()
                if projection.lifecycle is target:
                    return projection
                assert projection.lifecycle is not OperationLifecycle.TERMINAL, projection
                await changes.wait(float("inf"))


async def _terminal(controller: OperationController) -> OperationPublicProjectionV1:
    return await await_terminal_projection(
        controller,
        definition_id=COMPONENTS_SETUP_DEFINITION_ID,
        subject_ref=COMPONENTS_OPERATION_SUBJECT,
        request_schema=OperationSchemaIdentityV1.from_model(
            schema_id=COMPONENTS_SETUP_DEFINITION_ID + ".request", schema_version=1, model_type=ProvisionMutationRequest
        ),
        deadline=time.monotonic() + 120,
    )


@pytest.mark.usefixtures("components_role")
def test_mcp_review_answers_are_refused_and_a_human_uses_only_their_own_issued_controller(
    tmp_path: Path,
    counting_proxy: CountingProxy,
) -> None:
    with service_record_runtime(tmp_path) as runtime, ExitStack() as scope:
        human = _frontend(runtime, OperationFrontendProjection.TUI)
        scope.callback(human.close)
        assert human.login_password(bytearray(PROFILE_INPUT, "utf-8")).status.denial is None
        external = _frontend(runtime, OperationFrontendProjection.EXTERNAL_CLIENT)
        scope.callback(external.close)
        assert human.attendance_inventory().candidates == ()
        ask = external.request_attendance()
        assert isinstance(ask, AttendancePending)
        assert human.decide_attendance(ask.attendance_id, approve=True).approved
        admitted = external.attendance_status(ask.attendance_id)
        assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=external)

        async def scenario() -> None:
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    submitted = tool_document(
                        await sdk.call_tool(
                            "execute",
                            {
                                "definition_id": COMPONENTS_SETUP_DEFINITION_ID,
                                "subject_ref": COMPONENTS_OPERATION_SUBJECT,
                                "payload": {},
                            },
                        )
                    )
                    operation = submitted["receipt"]["operation_id"]

                    async def read_mcp() -> OperationPublicProjectionV1:
                        document = tool_document(
                            await sdk.call_tool(
                                "observe",
                                {
                                    "observation": {"operation_id": operation, "after_cursor": 0, "page_limit": 32},
                                },
                            )
                        )
                        projection = OperationPublicProjectionV1.model_validate_json(
                            json.dumps(document["reply"]["observation"]["projection"])
                        )
                        return projection

                    try:
                        waiting = await _waiting(external, read_mcp)
                    except AssertionError:
                        result = await sdk.call_tool("result", {"result": {"operation_id": operation}})
                        raise AssertionError(result.structured_content) from None
                    pending = waiting.pending_interaction
                    assert isinstance(pending, OperationReviewAvailableInteractionV1)
                    for action in ("apply", "reject"):
                        refused = await sdk.call_tool(
                            "respond",
                            {
                                "action": action,
                                "operation_id": operation,
                                "interaction_id": pending.interaction_id,
                                "revision": pending.revision,
                            },
                        )
                        assert refused.is_error is True, refused
                        assert refused.structured_content is not None
                        assert refused.structured_content["code"] == "person_act_required"
                    # Attendance parentage and public coordinates confer no
                    # response bearer for the child's separate submission.
                    borrowed = OperationController(client=human, operation_id=operation, session_id=human.session_id)
                    control = await borrowed.response_control(
                        interaction_id=pending.interaction_id, revision=pending.revision
                    )
                    with pytest.raises(FrontendRefusedError) as missing_authority:
                        await control.inspect()
                    assert missing_authority.value.reason == "response_authority_required"
                    tool_document(
                        await sdk.call_tool(
                            "control",
                            {"action": "cancel", "operation_id": operation, "expected_revision": waiting.revision},
                        )
                    )
                    assert (
                        await _waiting(external, read_mcp, target=OperationLifecycle.TERMINAL)
                    ).effect is OperationEffect.NONE

                    controller = await OperationController.submit(
                        human,
                        definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                        subject_ref=COMPONENTS_OPERATION_SUBJECT,
                        payload=ProvisionMutationRequest(),
                    )
                    await controller.start()

                    async def read_human() -> OperationPublicProjectionV1:
                        observed = await controller.observe(0, page_limit=32)
                        assert isinstance(observed, OperationObservationSuccessV1)
                        return observed.projection

                    waiting_human = await _waiting(human, read_human)
                    pending_human = waiting_human.pending_interaction
                    assert isinstance(pending_human, OperationReviewAvailableInteractionV1)
                    unclaimed = await controller.response_control(
                        interaction_id=pending_human.interaction_id, revision=pending_human.revision
                    )
                    with pytest.raises(FrontendRefusedError) as missing_authority:
                        await unclaimed.inspect()
                    assert missing_authority.value.reason == "response_authority_required"
                    review = await controller.resolve_review(pending_human.review_reference, ProvisionReviewProjection)
                    assert review.outcome == "success"
                    claimed = await asyncio.to_thread(
                        human.operation,
                        OperationReviewClaim(
                            request_id=uuid4(),
                            profile_id=human.profile_id,
                            session_id=controller.session_id,
                            reference=pending_human.review_reference,
                            reviewed_document_digest=content_hash_hex(
                                review.model_dump(mode="json", serialize_as_any=True)
                            ),
                        ),
                        deadline=time.monotonic() + 30,
                    )
                    assert isinstance(claimed, OperationReviewClaimed)
                    assert claimed.reference.revision == pending_human.revision + 1
                    own_control = await controller.response_control(
                        interaction_id=claimed.reference.interaction_id, revision=claimed.reference.revision
                    )
                    available = await own_control.inspect()
                    assert available.outcome == "success"
                    rejected = await own_control.reject(
                        OperationResponseRejectRequestV1(
                            operation_id=controller.operation_id,
                            interaction_id=claimed.reference.interaction_id,
                            revision=claimed.reference.revision,
                            actor_ref=controller.actor_ref,
                            responded_at=now(),
                        )
                    )
                    assert rejected.outcome == "success"
                    terminal = await _terminal(controller)
                    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert terminal.effect is OperationEffect.NONE
                    result = await controller.read_settled_result(terminal, ProvisionResult, result_version=1)
                    assert result.outcome.value == "rejected"
                    assert counting_proxy.tunnels == {}
            finally:
                await adapter.close()

        asyncio.run(scenario())
