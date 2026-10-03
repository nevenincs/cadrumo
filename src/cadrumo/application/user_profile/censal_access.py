"""Shared exact-profile access stages for recorded censal operations."""

from __future__ import annotations

from pydantic import BaseModel

from ..operations.access_resolution import (
    OBSERVATION_DISCLOSING_ACTIONS,
    OperationAccessContext,
    OperationAccessProfile,
    OperationPeriodScope,
    OperationResultSchemaPin,
    ResolvedOperationAccess,
    bind_replayed_period_independent_access,
)
from ..operations.models import OperationRequest
from .access_contracts import AccessAction, Availability, DisclosureCategory


def bind_whole_profile_censal_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    actions: frozenset[AccessAction],
    provider: Availability,
) -> ResolvedOperationAccess:
    """Bind whole-profile censal work whose result discloses only profile values.

    A replay of an admitted submission must replay this profile's
    period-independent submission of the same operation.
    """
    return bind_replayed_period_independent_access(
        context,
        OperationAccessProfile(
            actions=actions,
            observed_by=OBSERVATION_DISCLOSING_ACTIONS,
            result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
            result_schema=OperationResultSchemaPin.REGISTERED,
            period_scope=OperationPeriodScope.WHOLE_PROFILE,
            requires_human=False,
            provider=provider,
        ),
        definition_id=request.definition_id,
    )
