"""Stand-ins for the supervisor seams a human-review operation drives."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationInteractionKind, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.interactions import OperationInteractionRequest, OperationPendingInteraction
from ..operations.models import OperationIdentity, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.persistence.journal import serialize_operation_operand


class PhasePrefixEvents:
    """Accept only phases under one operation's prefix and keep its effects."""

    def __init__(self, phase_prefix: str) -> None:
        self.phase_prefix = phase_prefix
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        assert phase.startswith(self.phase_prefix)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class ExclusiveIrreversibleSection:
    """Refuse a nested irreversible section and expose whether one is open."""

    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        assert not self.inside
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class ReviewOperands:
    """Operand store that resolves the reviewed proposal by its content digest."""

    def __init__(self, proposal_type: type[BaseModel]) -> None:
        self.proposal_type = proposal_type
        self.value: BaseModel | None = None
        self.proposal: BaseModel | None = None
        self.snapshot = None

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        if type(value).__name__ == "ReviewSnapshot":
            self.snapshot = value
        self.value = value
        return "d" * 64

    async def resolve(self, reference: str, model_type: type[BaseModel]) -> BaseModel:
        if model_type.__name__ == "ReviewSnapshot":
            assert self.snapshot is not None
            return self.snapshot
        assert self.proposal is not None and reference == sha256_hex(serialize_operation_operand(self.proposal))
        assert model_type is self.proposal_type
        return self.proposal


class ReviewInteractions:
    def __init__(self, operands: ReviewOperands) -> None:
        self.operands = operands
        self.pending: OperationPendingInteraction | None = None

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
        assert isinstance(reviewed_operand, self.operands.proposal_type)
        self.operands.proposal = reviewed_operand
        self.pending = OperationPendingInteraction.bind(
            request=OperationInteractionRequest(
                interaction_id=interaction_id,
                identity=identity,
                revision=revision,
                kind=OperationInteractionKind.REVIEW,
                presentation_code=presentation_code,
                response_schema_ref=response_schema_ref,
                continuation_digest=continuation_digest,
                expires_at=expires_at,
            ),
            response_token="e" * 64,
            reviewed_proposal_digest=sha256_hex(serialize_operation_operand(reviewed_operand)),
            baseline_digest=baseline_digest,
            proposed_effect_digest=proposed_effect_digest,
        )


def profile_operation_request(
    payload: BaseModel, definition_id: str, profile_id: UUID | str
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id, subject_ref=profile_operation_subject(str(profile_id)), payload=payload
    )


def review_execution_context(
    request: OperationRequest[BaseModel],
    operation: PinnedAuthorityOperation,
    *,
    phase_prefix: str,
    proposal_type: type[BaseModel],
):
    """Return the raw namespace, the typed context and the recording seams it holds."""
    events, operands, fence = (
        PhasePrefixEvents(phase_prefix),
        ReviewOperands(proposal_type),
        ExclusiveIrreversibleSection(),
    )
    interactions = ReviewInteractions(operands)
    value = SimpleNamespace(
        identity=OperationIdentity(
            operation_id="a" * 64, definition_id=request.definition_id, subject_ref=request.subject_ref
        ),
        revision=0,
        authority_operation=operation,
        events=events,
        operands=operands,
        cancellation=fence,
        interactions=interactions,
    )
    return value, cast(OperationExecutorContext, cast(object, value)), events, operands, fence, interactions
