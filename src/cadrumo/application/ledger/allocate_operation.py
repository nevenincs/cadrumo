"""Registered exact-profile allocation of one canonical ledger transaction."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...core.unit_proportion import is_unit_proportion
from ...domain.buckets.event import BucketEventId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.model_validation import classification_for_business_share
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_common import display_decimal
from .actions_manual import ledger_transaction_result_payload, update_manual_transaction_fields
from .id_resolution import resolve_transaction_id
from .models import LedgerTransactionResultPayload, ManualLedgerTransactionPatch, ManualLedgerTransactionResult
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_ALLOCATE_OPERATION_DEFINITION_ID = "ledger.allocate"
LEDGER_ALLOCATE_PHASE = "ledger.allocate"
_MAX_BUCKET_EVENT_IDS = 4096
_BusinessShareText = Annotated[str, Field(min_length=1, max_length=128)]
_BucketEventIds = Annotated[tuple[BucketEventId, ...], Field(max_length=_MAX_BUCKET_EVENT_IDS)]


class LedgerAllocateRequest(BaseModel):
    """Private exact-profile request; ``transaction_id`` may be a CLI prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    business_pct: _BusinessShareText
    category_id: Annotated[str, Field(max_length=128)] | None = None
    usage_ratio_id: Annotated[str, Field(max_length=128)] | None = None
    prorrata_reference: Annotated[str, Field(max_length=256)] | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("business_pct")
    @classmethod
    def _canonical_unit_proportion(cls, value: str) -> str:
        """Store only bounded canonical decimal text for the allocation share."""
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or not is_unit_proportion(parsed):
            raise ValueError("business_pct must be canonical decimal text within 0..1")
        return display_decimal(parsed)


class LedgerAllocateOperationResult(BaseModel):
    """Bounded display projection and effect receipt for one allocation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: _BucketEventIds = ()


class LedgerAllocateExecutor:
    """Apply the canonical allocation action with exact worker profile custody."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile service composition capability."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerAllocateRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Resolve the transaction and mutate it under a fresh commit boundary."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_ALLOCATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_ALLOCATE_PHASE)

        def prepare() -> tuple[LedgerActionPorts, ManualLedgerTransactionPatch]:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            for repository in (
                ports.invoice_repository,
                ports.work_unit_repository,
                ports.calculation_repository,
            ):
                if getattr(repository, "bucket_id", None) != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            share = try_parse_canonical_decimal(payload.business_pct, signed=False)
            if share is None:
                raise TransactionValidationError("business_pct must be canonical decimal text")
            allocation_classification = classification_for_business_share(share)
            category_id = payload.category_id
            if category_id is not None:
                category_id = require_spending_category(category_id.strip(), authority=operation).value
            patch_values: dict[str, object] = {
                "business_classification": allocation_classification,
                "business_pct": share,
            }
            if category_id is not None:
                patch_values["category_id"] = category_id
            if payload.usage_ratio_id is not None:
                patch_values["usage_ratio_id"] = payload.usage_ratio_id
            if payload.prorrata_reference is not None:
                patch_values["prorrata_reference"] = payload.prorrata_reference
            patch = ManualLedgerTransactionPatch.model_validate(patch_values)
            return ports, patch

        ports, patch = await asyncio.to_thread(prepare)

        def allocate() -> ManualLedgerTransactionResult:
            catalogue = ports.transaction_repository.load()
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            current = catalogue.transactions[transaction_id]
            return update_manual_transaction_fields(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                patch=patch,
                actor=payload.actor or bucket_id or "operator",
                source_command="aeat app ledger allocate",
                ports=ports,
                catalogue=catalogue,
                expected_current=current,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(allocate)
                projection = _operation_result(payload.profile_id, result)
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                return await context.operands.put(projection, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-allocate-commit")


def build_ledger_allocate_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare durable, exact-profile allocation with a bounded secure result."""
    return OperationDefinition(
        definition_id=LEDGER_ALLOCATE_OPERATION_DEFINITION_ID,
        request_type=LedgerAllocateRequest,
        result_type=LedgerAllocateOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerAllocateRequest,
            executor_type=LedgerAllocateExecutor,
            build=lambda: LedgerAllocateExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_ALLOCATE_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def _operation_result(profile_id: UUID, result: ManualLedgerTransactionResult) -> LedgerAllocateOperationResult:
    """Validate the exact profile and preserve only the canonical result payload."""
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerAllocateOperationResult(
        profile_id=profile_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
    )


def resolve_ledger_allocate_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and COMMIT for every allocation."""
    if request.definition_id != LEDGER_ALLOCATE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerAllocateRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_allocate_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request, bounded result, and profile access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerAllocateOperationResult,
        access_resolver=resolve_ledger_allocate_access,
    )


__all__ = [
    "LEDGER_ALLOCATE_OPERATION_DEFINITION_ID",
    "LEDGER_ALLOCATE_PHASE",
    "LedgerAllocateExecutor",
    "LedgerAllocateOperationResult",
    "LedgerAllocateRequest",
    "build_ledger_allocate_definition",
    "build_ledger_allocate_registration",
    "resolve_ledger_allocate_access",
]
