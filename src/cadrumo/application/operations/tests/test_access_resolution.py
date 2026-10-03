"""Shared mechanics that bind one operation's declared access policy to the host."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..access_resolution import (
    ADMISSION_ENTRY_ACTIONS,
    COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    OBSERVATION_DISCLOSING_ACTIONS,
    OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    bind_operation_access,
    operation_disclosures,
    require_admitted_submission,
    require_declared_frontend_and_action,
    require_period_independent_admission,
    require_period_independent_replay_or_authority,
    require_same_origin_admission,
    require_single_period_admission,
    with_commit_action,
)
from ..frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..registry import OperationFrontendProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_RESULT_SCHEMA_ID = "test.access.result"


def _context(action: AccessAction, *, result_schema_id: str | None = _RESULT_SCHEMA_ID) -> OperationAccessContext:
    schema = None if result_schema_id is None else SimpleNamespace(schema_id=result_schema_id)
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=cast(Any, SimpleNamespace(result_schema=schema, definition_contract_digest="c" * 64)),
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize("action", sorted(OBSERVATION_DISCLOSING_ACTIONS))
def test_observing_actions_disclose_only_the_operation_observation(action: AccessAction) -> None:
    context = _context(action)

    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
        result_schema_id=None,
    )

    assert [(d.destination_id, d.projection_id, d.category) for d in disclosures] == [
        (context.destination_id, OPERATION_OBSERVATION_PROJECTION_ID, DisclosureCategory.OPERATION_METADATA)
    ]


def test_an_action_outside_the_declared_observers_discloses_nothing() -> None:
    disclosures = operation_disclosures(
        _context(AccessAction.CANCEL),
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=None,
    )

    assert disclosures == frozenset()


@pytest.mark.parametrize("pinned", [None, _RESULT_SCHEMA_ID])
def test_result_discloses_the_registered_schema_in_the_declared_category(pinned: str | None) -> None:
    context = _context(AccessAction.RESULT)

    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=pinned,
    )

    assert [(d.destination_id, d.projection_id, d.category) for d in disclosures] == [
        (context.destination_id, _RESULT_SCHEMA_ID, DisclosureCategory.PROFILE_VALUES)
    ]


@pytest.mark.parametrize(
    ("registered", "pinned"),
    [(None, None), (None, _RESULT_SCHEMA_ID), ("test.access.other", _RESULT_SCHEMA_ID)],
    ids=["unregistered", "unregistered-pinned", "foreign-schema"],
)
def test_result_without_the_expected_registered_schema_is_unavailable(
    registered: str | None, pinned: str | None
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        operation_disclosures(
            _context(AccessAction.RESULT, result_schema_id=registered),
            observed_by=OBSERVATION_DISCLOSING_ACTIONS,
            result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
            result_schema_id=pinned,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_submission_discloses_nothing() -> None:
    disclosures = operation_disclosures(
        _context(AccessAction.SUBMIT),
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
        result_schema_id=None,
    )

    assert disclosures == frozenset()


def test_empty_periods_bind_period_independent_work() -> None:
    context = _context(AccessAction.SUBMIT)

    resolved = bind_operation_access(
        context,
        profile_id=_PROFILE,
        definition_id="test.access",
        actions=OPERATION_LIFECYCLE_ACTIONS,
        disclosures=frozenset(),
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=True,
        provider=Availability.NOT_REQUIRED,
    )

    assert resolved.request.period_independent is True
    assert resolved.request.periods == frozenset()
    assert resolved.request.destination_id == context.destination_id
    assert resolved.request.frontend is context.frontend
    assert resolved.request.action is AccessAction.SUBMIT
    assert resolved.policy.allow_period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.requires_human is True
    assert resolved.policy.backend is Availability.AVAILABLE
    assert resolved.policy.transaction_authority_required is False
    assert resolved.policy.definition_contract_digest == "c" * 64


def test_exact_periods_bind_period_restricted_work() -> None:
    period = Period.from_year_and_code(2026, "1T")

    resolved = bind_operation_access(
        _context(AccessAction.START),
        profile_id=_PROFILE,
        definition_id="test.access",
        actions=COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
        disclosures=frozenset(),
        periods=frozenset({period}),
        period_independent=False,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NEEDS_USER,
    )

    assert resolved.request.period_independent is False
    assert resolved.request.periods == frozenset({period})
    assert resolved.policy.periods == frozenset({period})
    assert resolved.policy.allow_period_independent is False
    assert resolved.policy.provider is Availability.NEEDS_USER
    assert AccessAction.COMMIT in resolved.policy.actions


def test_period_restricted_work_without_periods_is_not_widened_to_all_periods() -> None:
    with pytest.raises(ValidationError, match="provide exact periods"):
        bind_operation_access(
            _context(AccessAction.SUBMIT),
            profile_id=_PROFILE,
            definition_id="test.access",
            actions=OPERATION_LIFECYCLE_ACTIONS,
            disclosures=frozenset(),
            periods=frozenset(),
            period_independent=False,
            requires_all_periods=False,
            requires_human=False,
            provider=Availability.NOT_REQUIRED,
        )


def test_result_discloses_one_permission_per_declared_category() -> None:
    context = _context(AccessAction.RESULT)

    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}),
        result_schema_id=_RESULT_SCHEMA_ID,
    )

    assert {(d.projection_id, d.category) for d in disclosures} == {
        (_RESULT_SCHEMA_ID, DisclosureCategory.PROFILE_VALUES),
        (_RESULT_SCHEMA_ID, DisclosureCategory.TAX_VALUES),
    }


def _admitted(
    *,
    profile_id: UUID = _PROFILE,
    definition_id: str = "test.access",
    action: AccessAction = AccessAction.SUBMIT,
    periods: frozenset[Period] = frozenset(),
    destination_id: UUID | None = None,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=profile_id,
        definition_id=definition_id,
        action=action,
        frontend=frontend,
        periods=periods,
        period_independent=not periods,
        destination_id=destination_id or uuid4(),
    )


_PERIOD = Period.from_year_and_code(2026, "1T")


def test_single_period_admission_returns_the_admitted_period() -> None:
    admitted = _admitted(periods=frozenset({_PERIOD}))

    assert require_single_period_admission(admitted, profile_id=_PROFILE, definition_id="test.access") == frozenset(
        {_PERIOD}
    )


@pytest.mark.parametrize(
    "admitted",
    [
        _admitted(periods=frozenset({_PERIOD}), profile_id=uuid4()),
        _admitted(periods=frozenset({_PERIOD}), definition_id="test.other"),
        _admitted(periods=frozenset({_PERIOD}), action=AccessAction.START),
        _admitted(),
        _admitted(periods=frozenset({_PERIOD, Period.from_year_and_code(2026, "2T")})),
    ],
    ids=["other-profile", "other-definition", "not-a-submission", "period-independent", "two-periods"],
)
def test_single_period_admission_refuses_any_other_submission(admitted: OperationAccessRequest) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        require_single_period_admission(admitted, profile_id=_PROFILE, definition_id="test.access")

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_period_independent_admission_accepts_only_independent_submissions() -> None:
    require_period_independent_admission(_admitted(), profile_id=_PROFILE, definition_id="test.access")

    for admitted in (
        _admitted(periods=frozenset({_PERIOD})),
        _admitted(profile_id=uuid4()),
        _admitted(definition_id="test.other"),
        _admitted(action=AccessAction.RESUME),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            require_period_independent_admission(admitted, profile_id=_PROFILE, definition_id="test.access")
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_same_origin_admission_binds_destination_and_frontend() -> None:
    context = _context(AccessAction.OBSERVE)
    require_same_origin_admission(_admitted(destination_id=context.destination_id), context)

    for admitted in (
        _admitted(),
        _admitted(destination_id=context.destination_id, frontend=OperationFrontendProjection.TUI),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            require_same_origin_admission(admitted, context)
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_admitted_submission_accepts_either_period_scope_of_this_profiles_submission() -> None:
    require_admitted_submission(_admitted(), profile_id=_PROFILE, definition_id="test.access")
    require_admitted_submission(
        _admitted(periods=frozenset({_PERIOD})), profile_id=_PROFILE, definition_id="test.access"
    )

    for admitted in (
        _admitted(profile_id=uuid4()),
        _admitted(definition_id="test.other"),
        _admitted(action=AccessAction.OBSERVE),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            require_admitted_submission(admitted, profile_id=_PROFILE, definition_id="test.access")
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


_HELD_AUTHORITY = cast(Any, object())


def _replay_or_authority(context: OperationAccessContext) -> None:
    require_period_independent_replay_or_authority(context, profile_id=_PROFILE, definition_id="test.access")


@pytest.mark.parametrize("action", [AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.COMMIT])
def test_later_actions_replay_the_same_origin_period_independent_admission(action: AccessAction) -> None:
    context = _context(action)
    _replay_or_authority(replace(context, admitted_request=_admitted(destination_id=context.destination_id)))

    for admitted in (
        _admitted(),
        _admitted(destination_id=context.destination_id, periods=frozenset({_PERIOD})),
        _admitted(destination_id=context.destination_id, definition_id="test.other"),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            _replay_or_authority(replace(context, admitted_request=admitted, authority_operation=_HELD_AUTHORITY))
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("action", sorted(ADMISSION_ENTRY_ACTIONS))
def test_entry_actions_resolve_against_held_authority_instead_of_an_admission(action: AccessAction) -> None:
    context = replace(_context(action), admitted_request=_admitted(periods=frozenset({_PERIOD})))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _replay_or_authority(context)
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    _replay_or_authority(replace(context, authority_operation=_HELD_AUTHORITY))


def test_without_an_admission_every_action_requires_held_authority() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        _replay_or_authority(_context(AccessAction.OBSERVE))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    _replay_or_authority(replace(_context(AccessAction.OBSERVE), authority_operation=_HELD_AUTHORITY))


def test_an_undeclared_frontend_is_refused_before_an_undeclared_action() -> None:
    context = _context(AccessAction.COMMIT)
    cli = frozenset({OperationFrontendProjection.CLI})
    require_declared_frontend_and_action(context, frontends=cli, actions=frozenset({AccessAction.COMMIT}))

    with pytest.raises(ProfileAccessRefusedError) as frontend_refused:
        require_declared_frontend_and_action(
            context, frontends=frozenset({OperationFrontendProjection.TUI}), actions=frozenset({AccessAction.OBSERVE})
        )
    assert frontend_refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    with pytest.raises(ProfileAccessRefusedError) as action_refused:
        require_declared_frontend_and_action(context, frontends=cli, actions=frozenset({AccessAction.OBSERVE}))
    assert action_refused.value.reason is AccessDenialCode.OPERATION_DENIED


def test_commit_door_is_added_to_the_policy_and_nothing_else_changes() -> None:
    resolved = bind_operation_access(
        _context(AccessAction.SUBMIT),
        profile_id=_PROFILE,
        definition_id="test.access",
        actions=OPERATION_LIFECYCLE_ACTIONS,
        disclosures=frozenset(),
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )

    committing = with_commit_action(resolved)

    assert AccessAction.COMMIT not in resolved.policy.actions
    assert committing.policy.actions == COMMITTING_OPERATION_LIFECYCLE_ACTIONS
    assert committing.request == resolved.request
    assert committing.policy.model_dump(exclude={"actions"}) == resolved.policy.model_dump(exclude={"actions"})
