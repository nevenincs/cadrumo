"""Operation response management and human review claims for profile workers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, JsonValue, TypeAdapter

from cadrumo.adapters.persistence.storage.errors import RepositoryError
from cadrumo.application.operations.frontend_projection import OperationReviewProjectionReferenceV1
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.interactions import (
    OperationResponseIntent,
    OperationReviewClaimAttribution,
)
from cadrumo.application.operations.models import (
    OperationId,
    OperationStoredInvocation,
)
from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.operations import OperationInteractionKind, OperationLifecycle
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.operation_access import (
    CLAIMABLE_REVIEWS_MAX,
    OperationManagementRequest,
    operation_management_action,
)
from cadrumo_runtime.contracts.worker_authorization import RuntimeHumanReviewClaimAttestation

if TYPE_CHECKING:
    from cadrumo.application.operations.composition import OperationComposedServices, OperationSubmission
    from cadrumo.application.operations.interactions import OperationPendingInteraction, OperationResponseIntentValue
    from cadrumo.application.operations.projection_services import OperationResponseCapability
    from cadrumo.application.operations.registry import (
        OperationFrontendProjection,
        OperationRegistry,
    )
    from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorityRequest

    from .operation_host import ProfileWorkerOperationHost

_PROJECTION_DOCUMENT = TypeAdapter(dict[str, JsonValue])


@asynccontextmanager
async def manage_operation(
    host: ProfileWorkerOperationHost,
    session_id: UUID,
    request: OperationManagementRequest,
    *,
    frontend: OperationFrontendProjection,
) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
    """Serialize each exact response against a simultaneous human claim."""
    # A response without a submission this host holds is refused for authority in
    # `_manage`, whether or not the operation exists; only a held one reads its record.
    if (
        isinstance(request, OperationResponseControlRequestV1)
        and request.operation_id in host.submissions
        and _declares_review(host, (await host.stored_invocation(request.operation_id)).identity.definition_id)
    ):
        async with (
            host.serialize_review(request.operation_id),
            _manage_operation(host, session_id, request, frontend=frontend) as result,
        ):
            yield result
    else:
        async with _manage_operation(host, session_id, request, frontend=frontend) as result:
            yield result


def definition_declares_review(registry: OperationRegistry, definition_id: str) -> bool:
    """Whether the registered operation can ask a person to review, the only kind of interaction a person claims."""
    return OperationInteractionKind.REVIEW in registry.lookup_public_contract(definition_id).interaction_kinds


def _declares_review(host: ProfileWorkerOperationHost, definition_id: str) -> bool:
    return definition_declares_review(host.composed().submission.supervisor.registry, definition_id)


def _validate_claimed_response(
    host: ProfileWorkerOperationHost,
    request: OperationResponseControlRequestV1,
    session_id: UUID,
    frontend: OperationFrontendProjection,
) -> OperationResponseCapability:
    if not is_persons_frontend(frontend):
        raise ProfileAccessRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED)
    claim = host.review_claims.get(request.operation_id)
    if (
        claim is None
        or claim[0].session_id != session_id
        or claim[0].frontend != frontend
        or request.actor_ref != f"session:{session_id}"
        or request.revision != claim[1].revision
        or request.interaction_id != claim[1].interaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    return claim[3]


def _validate_response_authority(
    host: ProfileWorkerOperationHost,
    request: OperationManagementRequest,
    session_id: UUID,
    frontend: OperationFrontendProjection,
    claimed_response: OperationResponseControlRequestV1 | None,
) -> OperationResponseCapability | None:
    submission = host.submissions.get(request.operation_id)
    capability = None if submission is None else submission[1].response_capability
    if claimed_response is not None:
        capability = _validate_claimed_response(host, claimed_response, session_id, frontend)
    if isinstance(request, OperationResponseControlRequestV1) and (
        request.actor_ref != f"session:{session_id}"
        or submission is None
        or (claimed_response is None and submission[0] != session_id)
        or capability is None
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    return capability


async def _execute_control(
    host: ProfileWorkerOperationHost,
    request: OperationManagementRequest,
    submission: tuple[UUID, OperationSubmission] | None,
    capability: OperationResponseCapability | None,
) -> BaseModel:
    services = host.composed()
    if isinstance(request, OperationCancellationRequestV1):
        return await services.cancellation.request(request)
    if isinstance(request, OperationDetachRequestV1):
        return await services.detach.detach(request)
    # The exact original capability stays local. A new session,
    # idempotent receipt or reattached operation cannot obtain it.
    if submission is None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if isinstance(request, OperationResponseApplyRequestV1):
        response = await services.response(request, capability)
        return await response.apply(request)
    if isinstance(request, OperationResponseRejectRequestV1):
        response = await services.response(request, capability)
        return await response.reject(request)
    response = await services.inspect_response(request, capability)
    return await response.inspect(request)


def _management_guard(
    host: ProfileWorkerOperationHost,
    session_id: UUID,
    request: OperationManagementRequest,
    frontend: OperationFrontendProjection,
    claimed_response: OperationResponseControlRequestV1 | None,
    invocation: OperationStoredInvocation | None,
) -> AbstractAsyncContextManager[WorkerAuthorityRequest]:
    if claimed_response is None:
        return host.release(session_id, request.operation_id, frontend, operation_management_action(request))
    claim = host.review_claims.get(request.operation_id)
    submission = host.submissions.get(request.operation_id)
    if claim is None or host.execution is None or submission is None or invocation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    return host.execution.human_review_guard(invocation.identity, claim[0], submission[0])


@asynccontextmanager
async def _manage_operation(
    host: ProfileWorkerOperationHost,
    session_id: UUID,
    request: OperationManagementRequest,
    *,
    frontend: OperationFrontendProjection,
) -> AsyncGenerator[tuple[dict[str, JsonValue], WorkerAuthorityRequest]]:
    """Use canonical controls without recovering an earlier session's response proof."""
    submission = host.submissions.get(request.operation_id)
    response_request = request if isinstance(request, OperationResponseControlRequestV1) else None
    # Only a response to a submission this host holds reads its record: without one, every
    # response is refused for authority alone, whether or not the operation exists.
    invocation = (
        await host.stored_invocation(response_request.operation_id)
        if response_request is not None and submission is not None
        else None
    )
    # Cancellation and detach carry no interaction to answer, so they never take the
    # claimed-review path and keep the ordinary release guard. Only a response to a review
    # a person has claimed does: the original session's bearer was closed by that claim.
    claimed_response = (
        response_request
        if invocation is not None
        and response_request is not None
        and response_request.operation_id in host.review_claims
        else None
    )

    capability = _validate_response_authority(host, request, session_id, frontend, claimed_response)

    guard = _management_guard(host, session_id, request, frontend, claimed_response, invocation)
    async with guard as authorization:
        if claimed_response is not None and isinstance(
            request, OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1
        ):
            request = request.model_copy(update={"responded_at": now()})
        result = await await_cancellation_complete(
            _execute_control(host, request, submission, capability), task_name="profile-operation-control"
        )
        document = _PROJECTION_DOCUMENT.validate_python(result.model_dump(mode="json", serialize_as_any=True))
        yield document, authorization


async def claimable_reviews(
    host: ProfileWorkerOperationHost, proof: RuntimeHumanReviewClaimAttestation
) -> tuple[OperationId, ...]:
    """Name the live reviews the attested desktop person may claim now.

    Naming one grants nothing: the person still reads the review and
    claims it through the guarded claim, which rechecks every coordinate.
    A review another person holds is left out; one this person holds is
    named again so an interrupted answer can still be given.
    """
    if proof.frontend.value != "desktop":
        raise ProfileAccessRefusedError(AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    await host.custody.require_off_loop(proof.session_id)
    await host.require_current_inventory()
    if host.execution is None:
        return ()
    services = host.composed()
    named: list[OperationId] = []
    for operation_id, (original_session, _submission) in tuple(host.submissions.items()):
        if len(named) == CLAIMABLE_REVIEWS_MAX:
            break
        if await _is_claimable_review(host, operation_id, original_session, proof, services):
            named.append(operation_id)
    return tuple(named)


async def _is_claimable_review(
    host: ProfileWorkerOperationHost,
    operation_id: OperationId,
    original_session: UUID,
    proof: RuntimeHumanReviewClaimAttestation,
    services: OperationComposedServices,
) -> bool:
    try:
        invocation = await host.stored_invocation(operation_id)
        if not _declares_review(host, invocation.identity.definition_id):
            return False
        # A review whose original invocation lease retired can no longer be claimed.
        await host.custody.require_off_loop(original_session)
    except (AutomationCustodyError, ProfileAccessRefusedError):
        return False
    current = await services.submission.supervisor.inspect(operation_id)
    pending = current.pending_interaction
    if current.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION or pending is None:
        return False
    held = host.review_claims.get(operation_id)
    if held is not None:
        return held[0].model_copy(update={"verified_at": proof.verified_at}) == proof
    if pending.review_claim is not None:
        return False
    try:
        services.require_review_claimable(pending)
    except ValueError:
        return False
    return True


async def _existing_claim(
    host: ProfileWorkerOperationHost,
    proof: RuntimeHumanReviewClaimAttestation,
    reference: OperationReviewProjectionReferenceV1,
    reviewed_document_digest: ContentDigest,
    services: OperationComposedServices,
    pending: OperationPendingInteraction,
) -> tuple[OperationReviewProjectionReferenceV1, ContentDigest]:
    existing = host.review_claims[reference.operation_id]
    holder, held_reference, digest, _capability = existing
    # verified_at is an observation time, not a new login coordinate.
    if holder.model_copy(update={"verified_at": proof.verified_at}) != proof:
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_ALREADY_CLAIMED)
    attribution = pending.review_claim
    if attribution is None:
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
    source_reference = held_reference.model_copy(update={"revision": attribution.displayed_revision})
    if reference not in (held_reference, source_reference) or reviewed_document_digest != digest:
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
    current_review = await services.review.resolve(
        OperationReviewProjectionRequestV1(reference=held_reference), BaseModel
    )
    if (
        current_review.outcome != "success"
        or content_hash_hex(current_review.model_dump(mode="json", serialize_as_any=True)) != digest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
    try:
        services.require_review_claimable(pending)
    except ValueError:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED) from None
    return held_reference, digest


def _close_original_response(host: ProfileWorkerOperationHost, operation_id: OperationId) -> None:
    original = host.submissions.get(operation_id)
    if original is not None and original[1].response_capability is not None:
        original[1].response_capability.close()


async def _claim_unheld_review(
    host: ProfileWorkerOperationHost,
    proof: RuntimeHumanReviewClaimAttestation,
    reference: OperationReviewProjectionReferenceV1,
    reviewed_document_digest: ContentDigest,
    services: OperationComposedServices,
    pending: OperationPendingInteraction,
) -> OperationReviewProjectionReferenceV1:
    if pending.review_claim is not None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    rendered = await services.review.resolve(OperationReviewProjectionRequestV1(reference=reference), BaseModel)
    document = rendered.model_dump(mode="json", serialize_as_any=True)
    if rendered.outcome != "success" or content_hash_hex(document) != reviewed_document_digest:
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
    if pending.request.revision != reference.revision or pending.request.interaction_id != reference.interaction_id:
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
    try:
        services.require_review_claimable(pending)
    except ValueError:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED) from None
    attribution = OperationReviewClaimAttribution.model_validate(
        {
            "actor_ref": f"session:{proof.session_id}",
            "connection_id": proof.connection_id,
            "session_id": proof.session_id,
            "profile_id": proof.profile_binding.profile_id,
            "runtime_boot_id": proof.runtime_boot_id,
            "authority_generation": host.pinned().generation.logical_generation,
            "frontend": proof.frontend.value,
            "source_ref": proof.source_ref,
            "claimed_at": proof.verified_at,
            "displayed_revision": reference.revision,
            "reviewed_document_digest": reviewed_document_digest,
        }
    )
    try:
        successor = await await_cancellation_complete(
            services.submission.supervisor.claim_review(pending, attribution),
            task_name="profile-operation-review-claim",
        )
    except (RepositoryError, ValueError):
        raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE) from None
    try:
        capability = services.assign_review_actor(pending, successor)
    except ValueError:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED) from None
    _close_original_response(host, reference.operation_id)
    next_reference = reference.model_copy(update={"revision": successor.request.revision})
    host.review_claims[reference.operation_id] = proof, next_reference, reviewed_document_digest, capability
    return next_reference


@asynccontextmanager
async def claim_review(
    host: ProfileWorkerOperationHost,
    proof: RuntimeHumanReviewClaimAttestation,
    reference: OperationReviewProjectionReferenceV1,
    reviewed_document_digest: ContentDigest,
) -> AsyncGenerator[
    tuple[
        OperationReviewProjectionReferenceV1,
        ContentDigest,
        frozenset[OperationResponseIntentValue],
        WorkerAuthorityRequest,
    ]
]:
    """Commit attribution before rotating a live review's local bearer."""
    operation_id = reference.operation_id
    await host.custody.require_off_loop(proof.session_id)
    await host.require_current_inventory()
    services = host.composed()
    invocation = await host.stored_invocation(operation_id)
    if not _declares_review(host, invocation.identity.definition_id) or host.execution is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    submission = host.submissions.get(operation_id)
    if submission is None:
        raise ProfileAccessRefusedError(AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    async with (
        host.serialize_review(operation_id),
        host.execution.human_review_guard(invocation.identity, proof, submission[0]) as authorization,
    ):
        current = await services.submission.supervisor.inspect(operation_id)
        pending = current.pending_interaction
        if current.lifecycle is not OperationLifecycle.WAITING_FOR_INTERACTION or pending is None:
            raise ProfileAccessRefusedError(AccessDenialCode.REVIEW_CLAIM_STALE)
        existing = host.review_claims.get(operation_id)
        if existing is not None:
            held_reference, digest = await _existing_claim(
                host, proof, reference, reviewed_document_digest, services, pending
            )
            yield (
                held_reference,
                digest,
                frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
                authorization,
            )
            return
        next_reference = await _claim_unheld_review(host, proof, reference, reviewed_document_digest, services, pending)
        yield (
            next_reference,
            reviewed_document_digest,
            frozenset({OperationResponseIntent.APPLY, OperationResponseIntent.REJECT}),
            authorization,
        )
