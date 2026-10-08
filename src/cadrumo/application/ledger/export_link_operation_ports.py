"""Profile, disclosure and effect boundaries shared by ledger export and link."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect
from ...core.period import Period
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .commit_fence import LedgerCommitAttemptTracker
from .read_access import resolve_ledger_read_access


def resolve_export_link_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    profile_id: UUID,
    periods: frozenset[Period],
    requires_human: bool,
) -> ResolvedOperationAccess:
    """Keep current scope and require both identity-bearing and tax result consent."""
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=periods)
    disclosures = resolved.policy.disclosures
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id, projection_id=schema.schema_id, category=category
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | {AccessAction.COMMIT},
            "disclosures": disclosures,
            "requires_human": requires_human,
        }
    )
    return replace(resolved, policy=policy)


async def settle_export_link_failure(
    tracker: LedgerCommitAttemptTracker,
    context: OperationExecutorContext,
    *,
    confirmed_effect: OperationEffect = OperationEffect.PARTIAL,
) -> None:
    """Preserve confirmed earlier writes and admitted uncertain writer outcomes."""
    effect = (
        OperationEffect.UNKNOWN
        if tracker.has_uncertain_write
        else confirmed_effect
        if tracker.confirmed_write
        else OperationEffect.NONE
    )
    await context.events.effect(effect)
