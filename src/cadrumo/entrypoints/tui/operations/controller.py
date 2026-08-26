"""TUI-facing operation controller limited to the composed public service set.

The modal never inspects the operation supervisor, the journal reader, or any
other persistence-adjacent object directly. It drives one submitted operation
through exactly the composed public doors: submit, atomic observation,
registered REVIEW resolution, typed response control, cooperative
cancellation, detach, and the Workspace-refresh target resolver. Everything
this controller returns is a public frontend-contract model; nothing here
constructs or leaks a persisted snapshot, a journal record, or a
supervisor-private type.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from ....application.operations.composition import OperationComposedServices, OperationSubmission
from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.frontend_contracts import (
    OperationCancellationRequestV1,
    OperationCancellationResultV1,
    OperationDetachRequestV1,
    OperationDetachResultV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseControlResultV1,
    OperationResponseMutationResultV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionResultV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetResultV1,
)
from ....application.operations.interactions import OperationActorReference
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.replay import OperationReplayLimit
from ....application.operations.projection_services import OperationResponseControlService
from ....application.operations.registry import OperationSchemaIdentityV1
from ....core.identity import ContentDigest

_DEFAULT_PAGE_LIMIT: OperationReplayLimit = 256


@dataclass(frozen=True, slots=True)
class OperationController:
    """Drive one submitted operation through the composed public services only.

    Bound to exactly one already-submitted operation's receipt and its
    separately held, actor-bound response capability. The modal composes this
    once per detachable operation and never touches ``services`` directly.
    """

    services: OperationComposedServices
    submission: OperationSubmission
    actor_ref: OperationActorReference

    @property
    def operation_id(self) -> OperationId:
        """Return the exact operation identity this controller is bound to."""
        return self.submission.receipt.operation_id

    async def start(self) -> OperationId:
        """Start the bound submission through the composed submission door."""
        return await self.services.submission.start(self.operation_id)

    async def observe(
        self,
        after_cursor: OperationEventCursor,
        *,
        page_limit: OperationReplayLimit = _DEFAULT_PAGE_LIMIT,
    ) -> OperationObservationResultV1:
        """Return one atomic public projection plus its bounded event page."""
        return await self.services.observation.observe(
            OperationObservationRequestV1(
                operation_id=self.operation_id,
                after_cursor=after_cursor,
                page_limit=page_limit,
            )
        )

    async def resolve_review[ReviewProjectionT: BaseModel](
        self,
        reference: OperationReviewProjectionReferenceV1,
    ) -> OperationReviewProjectionResultV1[ReviewProjectionT]:
        """Resolve the exact registered safe REVIEW projection or a refusal."""
        return await self.services.review.resolve(OperationReviewProjectionRequestV1(reference=reference))

    async def response_control(
        self,
        *,
        interaction_id: str,
        revision: OperationRevision,
    ) -> OperationBoundResponseControl:
        """Bind this actor's response capability to the exact pending REVIEW."""
        request = OperationResponseControlRequestV1(
            operation_id=self.operation_id,
            interaction_id=interaction_id,
            revision=revision,
            actor_ref=self.actor_ref,
        )
        service = await self.services.response(request, self.submission.response_capability)
        return OperationBoundResponseControl(request=request, service=service)

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """Request cooperative cancellation at the exact expected revision."""
        return await self.services.cancellation.request(
            OperationCancellationRequestV1(operation_id=self.operation_id, expected_revision=expected_revision)
        )

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """Detach this frontend while the operation continues running durably."""
        return await self.services.detach.detach(
            OperationDetachRequestV1(operation_id=self.operation_id, expected_revision=expected_revision)
        )

    async def resolve_workspace_refresh[RefreshTargetT: BaseModel](
        self,
        *,
        terminal_revision: OperationRevision,
        definition_contract_digest: ContentDigest,
        target_schema: OperationSchemaIdentityV1,
    ) -> OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]:
        """Resolve the safe typed Workspace-refresh target after settlement."""
        return await self.services.refresh.resolve(
            OperationWorkspaceRefreshTargetRequestV1(
                operation_id=self.operation_id,
                terminal_revision=terminal_revision,
                definition_contract_digest=definition_contract_digest,
                target_schema=target_schema,
            )
        )


@dataclass(frozen=True, slots=True)
class OperationBoundResponseControl:
    """One actor-bound response-control handle scoped to a single REVIEW."""

    request: OperationResponseControlRequestV1
    service: OperationResponseControlService

    async def inspect(self) -> OperationResponseControlResultV1:
        """Return the currently authorized response intents or a refusal."""
        return await self.service.inspect(self.request)

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationResultV1:
        """Apply the exact pending REVIEW through the bound authority."""
        return await self.service.apply(request)

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationResultV1:
        """Reject the exact pending REVIEW through the bound authority."""
        return await self.service.reject(request)


__all__ = ["OperationBoundResponseControl", "OperationController"]
