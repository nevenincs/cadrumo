"""Trusted host context and owner-resolved policy for one operation boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ...core.period import Period
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .access_port import OperationAccessResolver
from .frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from .models import OperationRequest
from .operation_definition import OperationDefinition
from .registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

OPERATION_LIFECYCLE_ACTIONS = frozenset(
    {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
)
"""Submit, run, observe, read the result of, cancel and detach one invocation."""

COMMITTING_OPERATION_LIFECYCLE_ACTIONS = OPERATION_LIFECYCLE_ACTIONS | frozenset({AccessAction.COMMIT})
"""The operation lifecycle plus an explicit commit door."""

RESUMABLE_READ_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME, AccessAction.OBSERVE, AccessAction.RESULT}
)
"""Submit, run or resume, observe and read the result; never cancel or detach."""

RESUMABLE_COMMITTING_ACTIONS = RESUMABLE_READ_ACTIONS | frozenset({AccessAction.COMMIT})
"""The resumable read actions plus an explicit commit door."""

SINGLE_RUN_COMMITTING_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)
"""Submit, run once through an explicit commit door, observe and read the result."""

OBSERVATION_DISCLOSING_ACTIONS = frozenset({AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH})
"""Actions whose response shows the operation's own observation projection."""

ADMISSION_REPLAY_ACTIONS = frozenset(
    {AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.CANCEL, AccessAction.DETACH}
)
"""Actions that act on an already admitted submission instead of starting new work."""

ADMISSION_ENTRY_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME})
"""Actions that submit or (re)enter execution, so resolve against current authority."""


@dataclass(frozen=True, slots=True)
class OperationAccessContext:
    """Fresh host facts supplied only after resolving the registered definition."""

    profile_id: UUID
    destination_id: UUID
    action: AccessAction
    frontend: OperationFrontendProjection
    contract: OperationPublicDefinitionContractV1
    published_authority: Availability
    admitted_request: OperationAccessRequest | None = None
    authority_operation: PinnedAuthorityOperation | None = None


@dataclass(frozen=True, slots=True)
class ResolvedOperationAccess:
    """A domain resolution to be checked against current session authority."""

    request: OperationAccessRequest
    policy: OperationAccessPolicy


def with_commit_action(resolved: ResolvedOperationAccess) -> ResolvedOperationAccess:
    """Return ``resolved`` with the explicit COMMIT door added to its policy, nothing else changed."""
    # ``dict(model)`` keeps the nested permission models hashable inside their
    # frozen sets; python-mode serialization would turn them into dictionaries.
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def require_admitted_submission(admitted: OperationAccessRequest, *, profile_id: UUID, definition_id: str) -> None:
    """Require ``admitted`` to be this profile's submission of this operation, in either period scope."""
    if (
        admitted.profile_id != profile_id
        or admitted.definition_id != definition_id
        or admitted.action is not AccessAction.SUBMIT
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def require_single_period_admission(
    admitted: OperationAccessRequest, *, profile_id: UUID, definition_id: str
) -> frozenset[Period]:
    """Return the one period this profile's submission of the operation was admitted for."""
    require_admitted_submission(admitted, profile_id=profile_id, definition_id=definition_id)
    if admitted.period_independent or len(admitted.periods) != 1:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return admitted.periods


def require_period_independent_admission(
    admitted: OperationAccessRequest, *, profile_id: UUID, definition_id: str
) -> None:
    """Require this profile's submission of the operation to have been admitted period-independent."""
    require_admitted_submission(admitted, profile_id=profile_id, definition_id=definition_id)
    if admitted.periods or not admitted.period_independent:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def require_period_independent_replay_or_authority(
    context: OperationAccessContext, *, profile_id: UUID, definition_id: str
) -> None:
    """Require a replayed period-independent admission, or held authority for fresh work.

    Every action outside ``ADMISSION_ENTRY_ACTIONS`` on an admitted submission must
    replay this profile's period-independent admission of the operation. The
    replay binds no destination or frontend: a later session always has a new
    destination, its disclosures name that destination, and COMMIT is held to the
    originally approved scope by the host. Any other action, and any action
    without an admission, resolves against the host's held authority operation.
    """
    admitted = context.admitted_request
    if admitted is not None and context.action not in ADMISSION_ENTRY_ACTIONS:
        require_period_independent_admission(admitted, profile_id=profile_id, definition_id=definition_id)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def require_declared_frontend_and_action(
    context: OperationAccessContext,
    *,
    frontends: frozenset[OperationFrontendProjection],
    actions: frozenset[AccessAction],
) -> None:
    """Refuse a frontend, then an action, that the operation does not declare for this request."""
    if context.frontend not in frontends:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in actions:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def operation_disclosures(
    context: OperationAccessContext,
    *,
    observed_by: frozenset[AccessAction],
    result_categories: frozenset[DisclosureCategory],
    result_schema_id: str | None,
) -> frozenset[DisclosurePermission]:
    """Return the output the current action may show the requesting destination.

    Actions in ``observed_by`` show the operation's observation projection; RESULT
    shows the registered result schema in each of ``result_categories``.
    ``result_schema_id`` pins that schema when the operation names it, while
    ``None`` accepts the registered contract's own result schema. Every other
    action discloses nothing.
    """
    if context.action in observed_by:
        projection_id = OPERATION_OBSERVATION_PROJECTION_ID
        categories = frozenset({DisclosureCategory.OPERATION_METADATA})
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or (result_schema_id is not None and schema.schema_id != result_schema_id):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        projection_id = schema.schema_id
        categories = result_categories
    else:
        return frozenset[DisclosurePermission]()
    return frozenset(
        DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=projection_id,
            category=category,
        )
        for category in categories
    )


def bind_operation_access(
    context: OperationAccessContext,
    *,
    profile_id: UUID,
    definition_id: str,
    actions: frozenset[AccessAction],
    disclosures: frozenset[DisclosurePermission],
    periods: frozenset[Period],
    period_independent: bool,
    requires_all_periods: bool,
    requires_human: bool,
    provider: Availability,
) -> ResolvedOperationAccess:
    """Bind the host's current coordinates to one operation's declared access policy.

    The request scope is exactly ``periods`` or explicitly period-independent work,
    and the policy admits no wider scope; the access request refuses any other
    combination. The backend is available and no transaction authority is
    required: write authority is checked at each admitted transaction seam, and
    requiring it here would refuse ordinary operation access. An operation that
    needs either otherwise builds its policy directly.
    """
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=profile_id,
            definition_id=definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=periods,
            period_independent=period_independent,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=actions,
            disclosures=disclosures,
            periods=periods,
            allow_period_independent=period_independent,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=provider,
            transaction_authority_required=False,
            requires_human=requires_human,
            requires_all_periods=requires_all_periods,
        ),
    )


class OperationPeriodScope(StrEnum):
    """The period coordinates an access profile binds."""

    SELECTED_PERIODS = "selected_periods"
    """Exactly the periods the operation resolved; never period-independent work."""
    PERIOD_INDEPENDENT = "period_independent"
    """Period-independent work that needs no unrestricted period ceiling."""
    WHOLE_PROFILE = "whole_profile"
    """Period-independent work over every period, so the grant must be unrestricted."""


class OperationResultSchemaPin(StrEnum):
    """Which result schema RESULT may disclose."""

    REGISTERED = "registered"
    """The registered contract's own result schema."""
    DEFINITION_RESULT = "definition_result"
    """Only the schema named ``<definition_id>.result``."""


@dataclass(frozen=True, slots=True)
class OperationAccessProfile:
    """Every policy axis of one operation's access, apart from the host's coordinates."""

    actions: frozenset[AccessAction]
    observed_by: frozenset[AccessAction]
    result_categories: frozenset[DisclosureCategory]
    result_schema: OperationResultSchemaPin
    period_scope: OperationPeriodScope
    requires_human: bool
    provider: Availability


def bind_operation_access_profile(
    context: OperationAccessContext,
    profile: OperationAccessProfile,
    *,
    profile_id: UUID,
    definition_id: str,
    periods: frozenset[Period],
) -> ResolvedOperationAccess:
    """Bind the host's coordinates, the resolved periods and one named access profile.

    ``periods`` is the exact selection for a selected-periods profile and empty
    otherwise; the access request refuses any other combination.
    """
    pinned = profile.result_schema is OperationResultSchemaPin.DEFINITION_RESULT
    disclosures = operation_disclosures(
        context,
        observed_by=profile.observed_by,
        result_categories=profile.result_categories,
        result_schema_id=definition_id + ".result" if pinned else None,
    )
    return bind_operation_access(
        context,
        profile_id=profile_id,
        definition_id=definition_id,
        actions=profile.actions,
        disclosures=disclosures,
        periods=periods,
        period_independent=profile.period_scope is not OperationPeriodScope.SELECTED_PERIODS,
        requires_all_periods=profile.period_scope is OperationPeriodScope.WHOLE_PROFILE,
        requires_human=profile.requires_human,
        provider=profile.provider,
    )


def bind_replayed_or_fresh_single_period_access(
    context: OperationAccessContext,
    profile: OperationAccessProfile,
    *,
    definition_id: str,
    fresh_period: Callable[[PinnedAuthorityOperation], Period],
) -> ResolvedOperationAccess:
    """Bind the admitted period on replay, or the period read under held authority.

    An action in ``ADMISSION_REPLAY_ACTIONS`` on an admitted submission keeps the
    one period this profile's submission was admitted for. Any other action needs
    the host's held authority operation, under which ``fresh_period`` reads the
    addressed record's period.
    """
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        periods = require_single_period_admission(admitted, profile_id=context.profile_id, definition_id=definition_id)
    else:
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        periods = frozenset({fresh_period(context.authority_operation)})
    return bind_operation_access_profile(
        context, profile, profile_id=context.profile_id, definition_id=definition_id, periods=periods
    )


def bind_replayed_period_independent_access(
    context: OperationAccessContext, profile: OperationAccessProfile, *, definition_id: str
) -> ResolvedOperationAccess:
    """Bind period-independent access, replaying the admitted submission's scope on replay actions.

    An action in ``ADMISSION_REPLAY_ACTIONS`` on an admitted submission must replay
    this profile's period-independent admission of the operation. Fresh work needs
    no held authority because it binds no period.
    """
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        require_period_independent_admission(admitted, profile_id=context.profile_id, definition_id=definition_id)
    return bind_operation_access_profile(
        context, profile, profile_id=context.profile_id, definition_id=definition_id, periods=frozenset()
    )


# Named access profiles. A profile exists only where at least two resolvers
# declare exactly the same policy, and each resolver names its profile. The
# name spells every axis:
#   [HUMAN_]<ACTIONS>_<SCOPE>_<SCHEMA>_RESULT_<CATEGORIES>_VALUES_ACCESS
# - HUMAN_: only a human session may act.
# - ACTIONS: LIFECYCLE, COMMITTING_LIFECYCLE, RESUMABLE_READ,
#   RESUMABLE_COMMITTING or SINGLE_RUN_COMMITTING, the action sets above; every
#   declared observing action discloses the observation projection.
# - SCOPE: SELECTED_PERIODS, PERIOD_INDEPENDENT or WHOLE_PROFILE.
# - SCHEMA: REGISTERED or DEFINITION, the result schema RESULT may disclose.
# - CATEGORIES: TAX, PROFILE or PROFILE_AND_TAX, the result's disclosure categories.
# No named profile requires a provider. A policy that differs on any axis
# stays inline at its resolver.

LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=OPERATION_LIFECYCLE_ACTIONS,
    observed_by=OBSERVATION_DISCLOSING_ACTIONS,
    result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.REGISTERED,
    period_scope=OperationPeriodScope.SELECTED_PERIODS,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=OPERATION_LIFECYCLE_ACTIONS,
    observed_by=OBSERVATION_DISCLOSING_ACTIONS,
    result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.REGISTERED,
    period_scope=OperationPeriodScope.WHOLE_PROFILE,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    observed_by=OBSERVATION_DISCLOSING_ACTIONS,
    result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.REGISTERED,
    period_scope=OperationPeriodScope.SELECTED_PERIODS,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS = OperationAccessProfile(
    actions=OPERATION_LIFECYCLE_ACTIONS,
    observed_by=OBSERVATION_DISCLOSING_ACTIONS,
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
    result_schema=OperationResultSchemaPin.REGISTERED,
    period_scope=OperationPeriodScope.PERIOD_INDEPENDENT,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
COMMITTING_LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS = OperationAccessProfile(
    actions=COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    observed_by=OBSERVATION_DISCLOSING_ACTIONS,
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
    result_schema=OperationResultSchemaPin.REGISTERED,
    period_scope=OperationPeriodScope.PERIOD_INDEPENDENT,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS = OperationAccessProfile(
    actions=SINGLE_RUN_COMMITTING_ACTIONS,
    observed_by=frozenset({AccessAction.OBSERVE}),
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
    result_schema=OperationResultSchemaPin.DEFINITION_RESULT,
    period_scope=OperationPeriodScope.PERIOD_INDEPENDENT,
    requires_human=True,
    provider=Availability.NOT_REQUIRED,
)
HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=RESUMABLE_READ_ACTIONS,
    observed_by=frozenset({AccessAction.OBSERVE}),
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.DEFINITION_RESULT,
    period_scope=OperationPeriodScope.WHOLE_PROFILE,
    requires_human=True,
    provider=Availability.NOT_REQUIRED,
)
RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=RESUMABLE_READ_ACTIONS,
    observed_by=frozenset({AccessAction.OBSERVE}),
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.DEFINITION_RESULT,
    period_scope=OperationPeriodScope.WHOLE_PROFILE,
    requires_human=False,
    provider=Availability.NOT_REQUIRED,
)
HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS = OperationAccessProfile(
    actions=RESUMABLE_COMMITTING_ACTIONS,
    observed_by=frozenset({AccessAction.OBSERVE}),
    result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
    result_schema=OperationResultSchemaPin.DEFINITION_RESULT,
    period_scope=OperationPeriodScope.WHOLE_PROFILE,
    requires_human=True,
    provider=Availability.NOT_REQUIRED,
)


def _registered_operation_access(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
) -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    try:
        return (
            registry.lookup(request.definition_id),
            registry.lookup_public_registration(request.definition_id),
        )
    except KeyError:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None


def _require_registered_request(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
) -> OperationAccessResolver:
    resolver = registration.access_resolver
    if (
        resolver is None
        or type(request.payload) is not definition.request_type
        or context.contract != registration.contract
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolver


def _require_resolved_access_matches_host(
    resolved: ResolvedOperationAccess,
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
) -> None:
    access, policy = resolved.request, resolved.policy
    if (
        access.profile_id != context.profile_id
        or access.destination_id != context.destination_id
        or access.frontend is not context.frontend
        or access.action is not context.action
        or access.definition_id != request.definition_id
        or policy.definition_id != request.definition_id
        or policy.definition_contract_digest != context.contract.definition_contract_digest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def resolve_operation_access(
    *, registry: OperationRegistry, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> ResolvedOperationAccess:
    """Require an exact live registration and validate every host-owned coordinate."""
    definition, registration = _registered_operation_access(registry, request)
    resolver = _require_registered_request(definition, registration, request, context)
    resolved = resolver(request, context)
    _require_resolved_access_matches_host(resolved, request, context)
    return resolved
