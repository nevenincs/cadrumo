"""The operation doors consumed by a TUI modal, independent of hosting."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from cadrumo_client.contracts.operation_access import OperationReviewClaimed

from ....application.operations.error_detail import OperationErrorDetailV1
from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationResponseControlResultV1,
    OperationResponseMutationResultV1,
    OperationReviewProjectionResultV1,
)
from ....application.operations.frontend_projection import (
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from ....application.operations.frontend_requests import (
    OperationObservationResultV1,
    OperationResponseApplyRequestV1,
    OperationResponseRejectRequestV1,
)
from ....application.operations.interactions import OperationActorReference
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.replay import OperationReplayLimit


class OperationResponseControlPort(Protocol):
    """Inspect or answer one exact pending review through its authority owner."""

    async def inspect(self) -> OperationResponseControlResultV1:
        """Read current response permission without consuming it."""
        ...

    async def apply(self, request: OperationResponseApplyRequestV1) -> OperationResponseMutationResultV1:
        """Apply the bound review once, subject to fresh authority."""
        ...

    async def reject(self, request: OperationResponseRejectRequestV1) -> OperationResponseMutationResultV1:
        """Reject the bound review once, subject to fresh authority."""
        ...


class OperationControllerPort(Protocol):
    """One immutable submitted-operation binding; IDs alone confer no authority."""

    @property
    def operation_id(self) -> OperationId:
        """Return the operation rendered by this modal."""
        ...

    @property
    def actor_ref(self) -> OperationActorReference:
        """Return the actor bound at submission."""
        ...

    async def start(self) -> OperationId:
        """Request execution admission, not settlement."""
        ...

    async def observe(
        self, after_cursor: OperationEventCursor, *, page_limit: OperationReplayLimit = 256
    ) -> OperationObservationResultV1:
        """Read the canonical bounded projection and event page."""
        ...

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        """Read only the registered review projection."""
        ...

    async def response_control(
        self, *, interaction_id: str, revision: OperationRevision
    ) -> OperationResponseControlPort:
        """Bind controls without reconstructing a response capability."""
        ...

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """Request cancellation without claiming rollback."""
        ...

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """Request the definition's supported detach behavior."""
        ...


@runtime_checkable
class OperationReviewClaimPort(Protocol):
    """Explicit runtime claim of the exact review document displayed to a person."""

    async def resolve_review_document[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> tuple[OperationReviewProjectionResultV1[ReviewT], str]:
        """Read a typed review and the digest of that same complete envelope."""
        ...

    async def claim_review(
        self, reference: OperationReviewProjectionReferenceV1, reviewed_document_digest: str
    ) -> OperationReviewClaimed:
        """Claim only after the person has seen the document."""
        ...


@runtime_checkable
class OperationErrorDetailPort(Protocol):
    """A controller that can read a settled operation's recorded public error detail."""

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        """Read a refused or failed operation's recorded detail, or ``None`` when it has none."""
        ...


class OperationChangeWaiterPort(Protocol):
    """Wakes an observer when its operation may have advanced; it carries no operation fact."""

    @property
    def armed(self) -> bool:
        """Whether the cue is subscribed, so a wait can end on it."""
        ...

    def arm(self) -> None:
        """Subscribe on first use, then forget earlier cues; call before the observation the next wait follows."""
        ...

    async def wait(self, timeout: float) -> None:
        """Wait until a cue since the last arm, or until ``timeout`` seconds pass."""
        ...

    def close(self) -> None:
        """Stop receiving cues."""
        ...


@runtime_checkable
class OperationChangeSourcePort(Protocol):
    """A controller whose runtime cues it when the operation advances, so nothing need re-read on a timer."""

    def operation_changes(self) -> OperationChangeWaiterPort:
        """A new waiter on this controller's connection."""
        ...
