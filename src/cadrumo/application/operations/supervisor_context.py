"""Private executor context assembled by the operation supervisor."""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime

from pydantic import BaseModel

from ...core.operations import OperationInteractionKind
from ._execution_context import DefinitionBoundContext
from .financial_operand_submission import BoundTransientFinancialOperandAccess
from .interactions import OperationInteractionRequest, OperationPendingInteraction
from .models import OperationIdentity
from .persistence.journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from .projection_services import OperationResponseAuthorityIssuer
from .secret_submission import BoundEphemeralSecretAccess


def _new_response_token() -> str:
    """Create one unpersisted capability bearer for an exact REVIEW checkpoint."""
    return secrets.token_hex(32)


class _SupervisorInteractionAccess:
    """Publish reviewed operands through secure storage before journal visibility."""

    def __init__(
        self,
        *,
        request_pending: Callable[[OperationPendingInteraction], Awaitable[None]],
        operands: OperationSecureReferenceStore | None,
        clock: Callable[[], datetime],
        response_authority_issuer: OperationResponseAuthorityIssuer | None,
        response_token_factory: Callable[[], str],
    ) -> None:
        self._request_pending = request_pending
        self._operands = operands
        self._clock = clock
        self._response_authority_issuer = response_authority_issuer
        self._response_token_factory = response_token_factory

    async def request(self, pending: OperationPendingInteraction) -> None:
        await self._request_pending(pending)

    async def publish_review(
        self,
        *,
        interaction_id: str,
        identity: OperationIdentity,
        revision: int,
        presentation_code: str,
        response_schema_ref: str,
        continuation_digest: str,
        expires_at: datetime | None,
        reviewed_operand: BaseModel,
        baseline_digest: str | None = None,
        proposed_effect_digest: str | None = None,
    ) -> None:
        if self._operands is None:
            raise ValueError("secure review publication requires an operand store")
        reference = await self._operands.put(reviewed_operand, written_at=self._clock())
        request = OperationInteractionRequest(
            interaction_id=interaction_id,
            identity=identity,
            revision=revision,
            kind=OperationInteractionKind.REVIEW,
            presentation_code=presentation_code,
            response_schema_ref=response_schema_ref,
            continuation_digest=continuation_digest,
            expires_at=expires_at,
        )
        response_token = self._response_token_factory()
        try:
            pending = OperationPendingInteraction.bind(
                request=request,
                response_token=response_token,
                reviewed_proposal_digest=reference,
                baseline_digest=baseline_digest,
                proposed_effect_digest=proposed_effect_digest,
            )
            await self._request_pending(pending)
            if self._response_authority_issuer is not None:
                self._response_authority_issuer.issue(pending, response_token)
        finally:
            response_token = ""


class _SupervisorExecutorContext:
    """Delegate definition checks while adding supervisor-owned secure publication."""

    def __init__(
        self,
        *,
        context: DefinitionBoundContext,
        operands: OperationSecureReferenceStore | None,
        ephemeral_secret: BoundEphemeralSecretAccess,
        financial_operand: BoundTransientFinancialOperandAccess,
        clock: Callable[[], datetime],
        response_authority_issuer: OperationResponseAuthorityIssuer | None,
        response_token_factory: Callable[[], str],
    ) -> None:
        self.identity = context.identity
        self.cancellation = context.cancellation
        self.deadlines = context.deadlines
        self.events = context.events
        self._operands = operands
        self.ephemeral_secret = ephemeral_secret
        self.financial_operand = financial_operand
        self.cleanup = context.cleanup
        self.interactions = _SupervisorInteractionAccess(
            request_pending=context.interactions.request,
            operands=operands,
            clock=clock,
            response_authority_issuer=response_authority_issuer,
            response_token_factory=response_token_factory,
        )
        self._context = context

    @property
    def operands(self) -> OperationSecureReferenceStore:
        """Expose secure storage only when the composition root supplied it."""
        if self._operands is None:
            raise ValueError("operation definition has no secure operand store")
        return self._operands

    @property
    def revision(self) -> int:
        """Return the current durable revision without exposing journal state."""
        return self._context.snapshot.revision

    @property
    def snapshot(self) -> OperationPersistedSnapshot:
        """Expose the current durable view retained by the definition-bound context."""
        return self._context.snapshot
