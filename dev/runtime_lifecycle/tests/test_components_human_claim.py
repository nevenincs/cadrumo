"""Native runtime claim admission, independent human custody and exact response fencing.

The runtime fixture uses explicit native-login observation ports with real encrypted
profiles, worker processes, public transport and the built component PLAN role.
"""

import asyncio
import time
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_SETUP_DEFINITION_ID,
    ProvisionMutationRequest,
)
from cadrumo.application.operations.frontend_projection import OperationReviewAvailableInteractionV1
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import OperationEffect, OperationLifecycle
from cadrumo.core.time.clock import now
from cadrumo.tests.components_role_package import components_role_fixture, staged_components_role_fixture
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.operation_access import (
    OperationControl,
    OperationManage,
    OperationManaged,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationReview,
    OperationReviewClaim,
    OperationReviewClaimed,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

from .test_components_review import _frontend, _waiting

__all__ = ["components_role_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


def _claim(client: FrontendClient, reference, digest: str):
    return client.operation(
        OperationReviewClaim(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            reference=reference,
            reviewed_document_digest=digest,
        ),
        deadline=time.monotonic() + 30,
    )


def _person(runtime):
    wire = VerifiedConnection(
        runtime.endpoint.connect(timeout=3),
        expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )
    return FrontendClient(wire, profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI), wire


@pytest.mark.usefixtures("components_role")
@pytest.mark.parametrize("retire", [None, "invocation", "claimant", "past_time"])
def test_independent_humans_claim_mcp_review_once_and_both_live_principals_are_required(
    tmp_path: Path,
    retire: str | None,
) -> None:
    with service_record_runtime(tmp_path) as runtime, ExitStack() as scope:
        parent = _frontend(runtime, OperationFrontendProjection.TUI)
        scope.callback(parent.close)
        parent.login_password(bytearray(PROFILE_INPUT, "utf-8"))
        external = _frontend(runtime, OperationFrontendProjection.EXTERNAL_CLIENT)
        scope.callback(external.close)
        assert parent.attendance_inventory().candidates == ()
        ask = external.request_attendance()
        assert isinstance(ask, AttendancePending)
        assert parent.decide_attendance(ask.attendance_id, approve=True).approved
        assert isinstance(external.attendance_status(ask.attendance_id), ProfileStatus)
        admitted_people = [_person(runtime) for _ in range(2)]
        people = [item[0] for item in admitted_people]
        for person in people:
            scope.callback(person.close)
            person.login_password(bytearray(PROFILE_INPUT, "utf-8"))

        async def scenario() -> None:
            submitted = await asyncio.to_thread(
                external.operation,
                OperationSubmit(
                    request_id=uuid4(),
                    profile_id=external.profile_id,
                    session_id=external.session_id,
                    definition_id=COMPONENTS_SETUP_DEFINITION_ID,
                    subject_ref=COMPONENTS_OPERATION_SUBJECT,
                    payload_json=ProvisionMutationRequest().model_dump_json(),
                ),
                deadline=time.monotonic() + 30,
            )
            assert isinstance(submitted, OperationSubmitted)
            operation_id = submitted.receipt.operation_id
            await asyncio.to_thread(
                external.operation,
                OperationControl(
                    action="operation_start",
                    request_id=uuid4(),
                    profile_id=external.profile_id,
                    session_id=external.session_id,
                    operation_id=operation_id,
                ),
                deadline=time.monotonic() + 30,
            )

            async def read():
                observed = await asyncio.to_thread(
                    external.operation,
                    OperationObserve(
                        request_id=uuid4(),
                        profile_id=external.profile_id,
                        session_id=external.session_id,
                        observation=OperationObservationRequestV1(
                            operation_id=operation_id, after_cursor=0, page_limit=32
                        ),
                    ),
                    deadline=time.monotonic() + 30,
                )
                assert isinstance(observed, OperationObserved)
                assert isinstance(observed.observation, OperationObservationSuccessV1)
                return observed.observation.projection

            waiting = await _waiting(external, read)
            pending = waiting.pending_interaction
            assert isinstance(pending, OperationReviewAvailableInteractionV1)
            reference = pending.review_reference
            person = people[0]
            rendered = await asyncio.to_thread(
                person.operation,
                OperationReview(
                    request_id=uuid4(),
                    profile_id=person.profile_id,
                    session_id=person.session_id,
                    review=OperationReviewProjectionRequestV1(reference=reference),
                ),
                deadline=time.monotonic() + 30,
            )
            assert isinstance(rendered, OperationProjected)
            digest = content_hash_hex(rendered.document)
            with pytest.raises(FrontendRefusedError, match="person_act_required"):
                await asyncio.to_thread(_claim, external, reference, digest)
            for response in (
                OperationResponseControlRequestV1(
                    operation_id=operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=f"session:{external.session_id}",
                ),
                OperationResponseApplyRequestV1(
                    operation_id=operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=f"session:{external.session_id}",
                    responded_at=now(),
                ),
                OperationResponseRejectRequestV1(
                    operation_id=operation_id,
                    interaction_id=pending.interaction_id,
                    revision=pending.revision,
                    actor_ref=f"session:{external.session_id}",
                    responded_at=now(),
                ),
            ):
                with pytest.raises(FrontendRefusedError, match="person_act_required"):
                    await asyncio.to_thread(
                        external.operation,
                        OperationManage(
                            request_id=uuid4(),
                            profile_id=external.profile_id,
                            session_id=external.session_id,
                            management=response,
                        ),
                        deadline=time.monotonic() + 30,
                    )
            with pytest.raises(FrontendRefusedError, match="review_claim_stale"):
                await asyncio.to_thread(_claim, person, reference, "0" * 64)
            host = runtime.profiles._profiles[runtime.profile_id]
            with host.guard:
                current = host.authority._sessions[person.session_id]
                host.authority._sessions[person.session_id] = current.model_copy(
                    update={
                        "scope": current.scope.model_copy(
                            update={"actions": current.scope.actions - {AccessAction.REVIEW}}
                        ),
                    }
                )
            try:
                with pytest.raises(FrontendRefusedError, match="operation_denied"):
                    await asyncio.to_thread(_claim, person, reference, digest)
            finally:
                with host.guard:
                    host.authority._sessions[person.session_id] = current
            results = await asyncio.gather(
                *(asyncio.to_thread(_claim, candidate, reference, digest) for candidate in people),
                return_exceptions=True,
            )
            success = [
                (people[index], result)
                for index, result in enumerate(results)
                if isinstance(result, OperationReviewClaimed)
            ]
            assert len(success) == 1, results
            failures = [result for result in results if isinstance(result, FrontendRefusedError)]
            assert len(failures) == 1 and failures[0].reason == "review_already_claimed"
            holder, claimed = success[0]
            assert claimed.reference.revision == reference.revision + 1
            again = await asyncio.to_thread(_claim, holder, claimed.reference, digest)
            assert isinstance(again, OperationReviewClaimed)
            assert (again.reference, again.reviewed_document_digest, again.allowed_intents) == (
                claimed.reference,
                digest,
                claimed.allowed_intents,
            )
            duplicate = await asyncio.to_thread(_claim, holder, reference, digest)
            assert isinstance(duplicate, OperationReviewClaimed) and duplicate.reference == claimed.reference
            stored = await OperationJournalRepository(storage_root=runtime.root).load(operation_id)
            assert stored.revision == claimed.reference.revision
            forged_time = now() + timedelta(days=-3650 if retire == "past_time" else 3650)

            async def respond(*, reject: bool = False):
                response = (
                    OperationResponseRejectRequestV1(
                        operation_id=operation_id,
                        interaction_id=claimed.reference.interaction_id,
                        revision=claimed.reference.revision,
                        actor_ref=f"session:{holder.session_id}",
                        responded_at=forged_time,
                    )
                    if reject
                    else OperationResponseControlRequestV1(
                        operation_id=operation_id,
                        interaction_id=claimed.reference.interaction_id,
                        revision=claimed.reference.revision,
                        actor_ref=f"session:{holder.session_id}",
                    )
                )
                return await asyncio.to_thread(
                    holder.operation,
                    OperationManage(
                        request_id=uuid4(),
                        profile_id=holder.profile_id,
                        session_id=holder.session_id,
                        management=response,
                    ),
                    deadline=time.monotonic() + 30,
                )

            inspected = await respond()
            assert isinstance(inspected, OperationManaged) and inspected.document["outcome"] == "success"
            if retire in {"invocation", "claimant"}:
                holder_session = holder.session_id
                holder_wire = next(wire for candidate, wire in admitted_people if candidate is holder)
                await asyncio.to_thread(
                    parent.revoke_session, external.session_id if retire == "invocation" else holder_session
                )
                refused = await asyncio.to_thread(
                    holder_wire.operation,
                    OperationManage(
                        request_id=uuid4(),
                        profile_id=holder.profile_id,
                        session_id=holder_session,
                        management=OperationResponseRejectRequestV1(
                            operation_id=operation_id,
                            interaction_id=claimed.reference.interaction_id,
                            revision=claimed.reference.revision,
                            actor_ref=f"session:{holder_session}",
                            responded_at=forged_time,
                        ),
                    ),
                    deadline=time.monotonic() + 30,
                )
                assert isinstance(refused, AccessRefusal)
                return
            decision_started = now()
            rejected = await respond(reject=True)
            assert isinstance(rejected, OperationManaged) and rejected.document["outcome"] == "success"
            terminal = await _waiting(external, read, target=OperationLifecycle.TERMINAL)
            assert terminal.effect is OperationEffect.NONE
            stored = await OperationJournalRepository(storage_root=runtime.root).load(operation_id)
            consumed = stored.consumed_interactions[0]
            assert decision_started <= consumed.consumed_at <= now()
            assert consumed.consumed_at != forged_time
            assert consumed.checkpoint.review_claim is not None
            assert consumed.checkpoint.review_claim.session_id == holder.session_id
            with pytest.raises(FrontendRefusedError, match="response_authority_required"):
                await respond()
            with pytest.raises(FrontendRefusedError, match="review_claim_stale"):
                await asyncio.to_thread(_claim, holder, claimed.reference, digest)

        asyncio.run(scenario())
