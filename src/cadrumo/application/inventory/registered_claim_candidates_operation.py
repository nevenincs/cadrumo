"""Registered read of the ledger transactions one inventory purchase may claim.

The list is the claim write's own gate applied to each active transaction, so a
frontend offers exactly the transactions the write would accept and words no
matching rule of its own.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.filing_year import FourDigitYear
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ..ledger.read_access import resolve_ledger_request_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalCondition,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import InventoryActividadNotFoundError, InventoryServiceInputError
from .movement_claim_checks import InventoryClaimCandidate
from .ports import InventoryServicePortsFactory
from .registered_executor import refusal_for_error
from .registered_projections import InventoryReasonFact, InventoryRefusalProjection
from .registered_requests import INVENTORY_NOT_FOUND_REFUSAL_CODE, INVENTORY_SERVICE_INPUT_REFUSAL_CODE
from .service import InventoryService

INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID = "ledger.inventory.movement.claim-candidates"


class InventoryClaimCandidatesRequest(BaseModel):
    """Ask which ledger transactions one purchase of one book may claim."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    actividad_id: str = Field(min_length=1)
    year: FourDigitYear
    movement_id: str = Field(min_length=1, max_length=64)


class InventoryClaimCandidateProjection(BaseModel):
    """One ledger transaction the purchase may claim, with what the ledger states of it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    booked_date: date
    counterparty: str | None
    description: str
    currency: str
    taxable_base: PublicDecimal | None
    iva_amount: PublicDecimal | None
    recargo_amount: PublicDecimal | None

    @classmethod
    def from_candidate(cls, candidate: InventoryClaimCandidate) -> InventoryClaimCandidateProjection:
        """Project one candidate, keeping a figure the ledger does not state as absent."""
        return cls(
            transaction_id=candidate.transaction_id,
            booked_date=candidate.booked_date,
            counterparty=candidate.counterparty,
            description=candidate.description,
            currency=candidate.currency,
            taxable_base=_public_or_none(candidate.taxable_base),
            iva_amount=_public_or_none(candidate.iva_amount),
            recargo_amount=_public_or_none(candidate.recargo_amount),
        )


def _public_or_none(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


class InventoryClaimCandidatesProjection(BaseModel):
    """The transactions a purchase may claim, or why the purchase cannot be asked about."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["listed", "refused"]
    profile_id: UUID
    actividad_id: str
    year: int
    movement_id: str
    candidates: tuple[InventoryClaimCandidateProjection, ...] = ()
    refusal: InventoryRefusalProjection | None = None

    @model_validator(mode="after")
    def _outcome_is_closed(self) -> InventoryClaimCandidatesProjection:
        if (self.outcome == "refused") != (self.refusal is not None) or (self.refusal is not None and self.candidates):
            raise ValueError("a refused candidate list carries only its refusal")
        return self


class InventoryClaimCandidatesExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InventoryClaimCandidatesProjection


class InventoryClaimCandidatesExecutor:
    """Answer the claimable transactions inside the exact profile's worker."""

    def __init__(self, ports_factory: InventoryServicePortsFactory) -> None:
        """Bind the bucket service factory the claim write also reads through."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[InventoryClaimCandidatesRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Check the exact profile, then list; nothing is written."""
        payload = request.payload
        if request.definition_id != INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID)
        bucket_id = str(payload.profile_id)

        def read() -> tuple[InventoryClaimCandidate, ...]:
            return InventoryService(ports=self._ports_factory(bucket_id=bucket_id)).movement_claim_candidates(
                bucket_id=bucket_id,
                actividad_id=payload.actividad_id,
                year=payload.year,
                movement_id=payload.movement_id,
            )

        async def answer() -> str | OperationRefusalEvidence:
            try:
                candidates = await asyncio.to_thread(read)
            except (InventoryActividadNotFoundError, InventoryServiceInputError) as error:
                detail = refusal_for_error(request=payload, error=error)
                if detail is None:
                    raise
                refusal = InventoryRefusalProjection(
                    code=detail.code,
                    reason=detail.reason,
                    actividad_id=detail.actividad_id,
                    year=detail.year,
                    movement_id=detail.movement_id,
                    reason_key=detail.reason_key,
                    reason_facts=tuple(
                        InventoryReasonFact(key=key, value=value) for key, value in sorted(detail.reason_facts.items())
                    ),
                    refusal_words=detail.refusal_words,
                    refusal_words_language=detail.refusal_words_language,
                )
                detail_ref = await context.operands.put(
                    InventoryClaimCandidatesExecutionResult(
                        result=_projection(payload, outcome="refused", refusal=refusal)
                    ),
                    written_at=now(),
                )
                await context.events.effect(OperationEffect.NONE)
                return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)
            reference = await context.operands.put(
                InventoryClaimCandidatesExecutionResult(
                    result=_projection(
                        payload,
                        outcome="listed",
                        candidates=tuple(InventoryClaimCandidateProjection.from_candidate(item) for item in candidates),
                    )
                ),
                written_at=now(),
            )
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(answer(), task_name="inventory-claim-candidates")


def _projection(
    request: InventoryClaimCandidatesRequest,
    *,
    outcome: Literal["listed", "refused"],
    candidates: tuple[InventoryClaimCandidateProjection, ...] = (),
    refusal: InventoryRefusalProjection | None = None,
) -> InventoryClaimCandidatesProjection:
    return InventoryClaimCandidatesProjection(
        outcome=outcome,
        profile_id=request.profile_id,
        actividad_id=request.actividad_id,
        year=request.year,
        movement_id=request.movement_id,
        candidates=candidates,
        refusal=refusal,
    )


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not InventoryClaimCandidatesExecutionResult:
        raise ValueError("invalid inventory claim candidates result")
    projection = result.result
    message = "inventory claim candidates has an incompatible terminal receipt"
    if projection.refusal is not None:
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.effect is not OperationEffect.NONE
            or receipt.refusal_ref != projection.refusal.code
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.identity.definition_id != INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID
        ):
            raise ValueError(message)
        return projection
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        effect=OperationEffect.NONE,
        message=message,
    )
    return projection


def build_inventory_claim_candidates_definition(ports_factory: InventoryServicePortsFactory) -> OperationDefinition:
    """Declare the exact-profile read of the transactions a purchase may claim."""
    return build_single_phase_definition(
        definition_id=INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID,
        request_type=InventoryClaimCandidatesRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InventoryClaimCandidatesExecutionResult,
        executor_type=InventoryClaimCandidatesExecutor,
        build=lambda: InventoryClaimCandidatesExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
        refusal_detail_codes=frozenset({INVENTORY_SERVICE_INPUT_REFUSAL_CODE, INVENTORY_NOT_FOUND_REFUSAL_CODE}),
    )


def resolve_inventory_claim_candidates_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every inventory read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID,
        request_type=InventoryClaimCandidatesRequest,
    )


def build_inventory_claim_candidates_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InventoryClaimCandidatesProjection,
        result_projector=_project_result,
        access_resolver=resolve_inventory_claim_candidates_access,
    )


__all__ = [
    "INVENTORY_CLAIM_CANDIDATES_OPERATION_DEFINITION_ID",
    "InventoryClaimCandidateProjection",
    "InventoryClaimCandidatesExecutionResult",
    "InventoryClaimCandidatesExecutor",
    "InventoryClaimCandidatesProjection",
    "InventoryClaimCandidatesRequest",
    "build_inventory_claim_candidates_definition",
    "build_inventory_claim_candidates_registration",
    "resolve_inventory_claim_candidates_access",
]
