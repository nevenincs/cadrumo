"""Registered exact-profile removal of one stored ledger classification rule."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_access import resolve_ledger_commit_access
from .rule_contracts import LedgerRuleRowProjection
from .rule_repository import LedgerClassificationRuleRepositoryFactory

LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID = "ledger.rule.remove"


class LedgerRuleRemoveRequest(BaseModel):
    """Exact profile, the rule's content-addressed id and the creation stamp it was listed with.

    A rule's id is a digest of its pattern, classification and category, so saving the
    same rule again keeps the id; only the creation stamp tells that save from the one
    the person looked at. Both must still match for the rule to be removed.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rule_id: Hex64Str
    expected_created_at: datetime


class LedgerRuleRemoveProjection(BaseModel):
    """What removal found: the removed rule, the rule that now differs, or nothing."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["removed", "not_found", "stale"]
    rule: LedgerRuleRowProjection | None = None

    @model_validator(mode="after")
    def _outcome_carries_its_row(self) -> LedgerRuleRemoveProjection:
        if (self.rule is None) != (self.outcome == "not_found"):
            raise ValueError("a rule removal names the stored rule exactly when one was found")
        return self


class LedgerRuleRemoveExecutor:
    """Remove one stored rule behind the runtime commit fence."""

    def __init__(self, repository_factory: LedgerClassificationRuleRepositoryFactory) -> None:
        """Bind the canonical encrypted rule repository factory."""
        self._repository_factory = repository_factory

    async def execute(
        self, request: OperationRequest[LedgerRuleRemoveRequest], context: OperationExecutorContext
    ) -> str:
        """Check the stored rule against what was listed, then delete it and publish the answer."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID)
        repository = await asyncio.to_thread(self._repository_factory, bucket_id=bucket_id)

        def found() -> LedgerRuleRemoveProjection:
            rule = next((rule for rule in repository.list_rules() if rule.rule_id == payload.rule_id), None)
            if rule is None:
                return LedgerRuleRemoveProjection(profile_id=payload.profile_id, outcome="not_found")
            outcome = "removed" if rule.created_at == payload.expected_created_at else "stale"
            return LedgerRuleRemoveProjection(
                profile_id=payload.profile_id, outcome=outcome, rule=LedgerRuleRowProjection.from_rule(rule)
            )

        async def remove() -> str:
            async with context.cancellation.irreversible_section():
                answer = await asyncio.to_thread(found)
                if answer.outcome != "removed":
                    await context.events.effect(OperationEffect.NONE)
                    return await context.operands.put(answer, written_at=now())
                await context.events.effect(OperationEffect.UNKNOWN)
                await asyncio.to_thread(repository.delete, payload.rule_id)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(answer, written_at=now())

        return await await_cancellation_complete(remove(), task_name="ledger-rule-remove")


def build_ledger_rule_remove_definition(
    repository_factory: LedgerClassificationRuleRepositoryFactory,
) -> OperationDefinition:
    """Declare one guarded, recorded rule removal with honest uncertain effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,
        request_type=LedgerRuleRemoveRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerRuleRemoveProjection,
        executor_type=LedgerRuleRemoveExecutor,
        build=lambda: LedgerRuleRemoveExecutor(repository_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    )


def resolve_ledger_rule_remove_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger commit rights for the exact profile."""
    if request.definition_id != LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerRuleRemoveRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_rule_remove_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRuleRemoveProjection,
        access_resolver=resolve_ledger_rule_remove_access,
    )


__all__ = [
    "LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID",
    "LedgerRuleRemoveExecutor",
    "LedgerRuleRemoveProjection",
    "LedgerRuleRemoveRequest",
    "build_ledger_rule_remove_definition",
    "build_ledger_rule_remove_registration",
    "resolve_ledger_rule_remove_access",
]
