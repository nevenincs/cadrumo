"""Named access profiles declare exactly the policy their names spell."""

from __future__ import annotations

import re
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from ....core.period import Period
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import access_resolution as access_module
from ..access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    OperationAccessProfile,
    OperationPeriodScope,
    OperationResultSchemaPin,
    bind_operation_access_profile,
    bind_replayed_or_fresh_single_period_access,
    bind_replayed_period_independent_access,
)
from ..registry import OperationFrontendProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_DEFINITION_ID = "test.access"
_PERIOD = Period.from_year_and_code(2026, "1T")

_PROFILE_NAMES = tuple(
    sorted(name for name, value in vars(access_module).items() if isinstance(value, OperationAccessProfile))
)
_PROFILE_NAME_GRAMMAR = re.compile(
    r"(?P<human>HUMAN_)?"
    r"(?P<actions>COMMITTING_LIFECYCLE|LIFECYCLE|RESUMABLE_READ|RESUMABLE_COMMITTING|SINGLE_RUN_COMMITTING)_"
    r"(?P<scope>SELECTED_PERIODS|PERIOD_INDEPENDENT|WHOLE_PROFILE)_"
    r"(?P<schema>REGISTERED|DEFINITION)_RESULT_"
    r"(?P<categories>PROFILE_AND_TAX|PROFILE|TAX)_VALUES_ACCESS"
)

_SUBMIT_RUN_OBSERVE_RESULT = {AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}
_LIFECYCLE = _SUBMIT_RUN_OBSERVE_RESULT | {AccessAction.RESUME, AccessAction.CANCEL, AccessAction.DETACH}


def _profile_named_by(profile_name: str) -> OperationAccessProfile:
    """Rebuild the policy a profile name promises, independently of its definition."""
    parsed = _PROFILE_NAME_GRAMMAR.fullmatch(profile_name)
    if parsed is None:
        raise ValueError(f"profile name does not spell an access policy: {profile_name}")
    actions = {
        "LIFECYCLE": _LIFECYCLE,
        "COMMITTING_LIFECYCLE": _LIFECYCLE | {AccessAction.COMMIT},
        "RESUMABLE_READ": _SUBMIT_RUN_OBSERVE_RESULT | {AccessAction.RESUME},
        "RESUMABLE_COMMITTING": _SUBMIT_RUN_OBSERVE_RESULT | {AccessAction.RESUME, AccessAction.COMMIT},
        "SINGLE_RUN_COMMITTING": _SUBMIT_RUN_OBSERVE_RESULT | {AccessAction.COMMIT},
    }[parsed["actions"]]
    categories = {
        "TAX": {DisclosureCategory.TAX_VALUES},
        "PROFILE": {DisclosureCategory.PROFILE_VALUES},
        "PROFILE_AND_TAX": {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES},
    }[parsed["categories"]]
    return OperationAccessProfile(
        actions=frozenset(actions),
        observed_by=frozenset(actions & {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}),
        result_categories=frozenset(categories),
        result_schema=(
            OperationResultSchemaPin.DEFINITION_RESULT
            if parsed["schema"] == "DEFINITION"
            else OperationResultSchemaPin.REGISTERED
        ),
        period_scope=OperationPeriodScope(parsed["scope"].lower()),
        requires_human=parsed["human"] is not None,
        provider=Availability.NOT_REQUIRED,
    )


def test_named_access_profiles_are_published() -> None:
    assert "LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS" in _PROFILE_NAMES
    assert all(name.endswith("_ACCESS") for name in _PROFILE_NAMES)


@pytest.mark.parametrize("profile_name", _PROFILE_NAMES)
def test_every_named_profile_declares_exactly_the_policy_its_name_spells(profile_name: str) -> None:
    assert getattr(access_module, profile_name) == _profile_named_by(profile_name)


def test_named_profiles_are_pairwise_distinct() -> None:
    profiles = [getattr(access_module, name) for name in _PROFILE_NAMES]

    for index, profile in enumerate(profiles):
        assert profile not in profiles[index + 1 :], _PROFILE_NAMES[index]


def test_profile_name_check_rejects_a_mislabelled_or_unspelled_profile() -> None:
    selected = LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS

    assert selected != _profile_named_by("LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS")
    assert selected != _profile_named_by("HUMAN_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS")
    assert selected != _profile_named_by("COMMITTING_LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS")
    assert selected != _profile_named_by("LIFECYCLE_SELECTED_PERIODS_DEFINITION_RESULT_TAX_VALUES_ACCESS")
    assert selected != _profile_named_by("LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_PROFILE_AND_TAX_VALUES_ACCESS")
    with pytest.raises(ValueError, match="does not spell"):
        _profile_named_by("DEFAULT_ACCESS")


def _context(action: AccessAction, *, result_schema_id: str) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=cast(
            Any,
            SimpleNamespace(
                result_schema=SimpleNamespace(schema_id=result_schema_id), definition_contract_digest="c" * 64
            ),
        ),
        published_authority=Availability.AVAILABLE,
    )


def test_a_selected_periods_profile_binds_exactly_the_resolved_periods() -> None:
    context = _context(AccessAction.RESULT, result_schema_id="any.registered.result")

    resolved = bind_operation_access_profile(
        context,
        LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=_PROFILE,
        definition_id=_DEFINITION_ID,
        periods=frozenset({_PERIOD}),
    )

    assert resolved.request.periods == frozenset({_PERIOD}) and not resolved.request.period_independent
    assert resolved.policy.periods == frozenset({_PERIOD})
    assert not resolved.policy.allow_period_independent and not resolved.policy.requires_all_periods
    assert resolved.policy.actions == LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS.actions
    assert not resolved.policy.requires_human
    assert {(d.projection_id, d.category) for d in resolved.policy.disclosures} == {
        ("any.registered.result", DisclosureCategory.TAX_VALUES)
    }


def test_a_whole_profile_profile_binds_unrestricted_period_independent_work() -> None:
    resolved = bind_operation_access_profile(
        _context(AccessAction.SUBMIT, result_schema_id="any.registered.result"),
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=_PROFILE,
        definition_id=_DEFINITION_ID,
        periods=frozenset(),
    )

    assert resolved.request.period_independent and resolved.request.periods == frozenset()
    assert resolved.policy.allow_period_independent and resolved.policy.requires_all_periods
    assert resolved.policy.disclosures == frozenset()


def test_a_whole_profile_profile_refuses_a_period_selection() -> None:
    with pytest.raises(ValueError, match="period-independent"):
        bind_operation_access_profile(
            _context(AccessAction.SUBMIT, result_schema_id="any.registered.result"),
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=_PROFILE,
            definition_id=_DEFINITION_ID,
            periods=frozenset({_PERIOD}),
        )


def test_a_definition_result_profile_discloses_only_the_definition_named_schema() -> None:
    profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS

    resolved = bind_operation_access_profile(
        _context(AccessAction.RESULT, result_schema_id=_DEFINITION_ID + ".result"),
        profile,
        profile_id=_PROFILE,
        definition_id=_DEFINITION_ID,
        periods=frozenset(),
    )

    assert resolved.policy.requires_human and not resolved.policy.requires_all_periods
    assert {(d.projection_id, d.category) for d in resolved.policy.disclosures} == {
        (_DEFINITION_ID + ".result", DisclosureCategory.PROFILE_VALUES)
    }
    with pytest.raises(ProfileAccessRefusedError) as refused:
        bind_operation_access_profile(
            _context(AccessAction.RESULT, result_schema_id="other.registered.result"),
            profile,
            profile_id=_PROFILE,
            definition_id=_DEFINITION_ID,
            periods=frozenset(),
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def _admitted(
    context: OperationAccessContext, *, definition_id: str = _DEFINITION_ID, periods: frozenset[Period]
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=definition_id,
        action=AccessAction.SUBMIT,
        frontend=context.frontend,
        periods=periods,
        period_independent=not periods,
        destination_id=context.destination_id,
    )


def _period_must_not_be_read(operation: object) -> Period:
    raise AssertionError("a replay or a refused fresh access must not read the addressed record")


def test_a_single_period_replay_keeps_the_admitted_period_without_reading() -> None:
    context = _context(AccessAction.RESULT, result_schema_id="any.registered.result")
    context = replace(context, admitted_request=_admitted(context, periods=frozenset({_PERIOD})))

    resolved = bind_replayed_or_fresh_single_period_access(
        context,
        LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
        fresh_period=_period_must_not_be_read,
    )

    assert resolved.request.periods == frozenset({_PERIOD})


@pytest.mark.parametrize(
    ("definition_id", "periods"),
    [
        ("test.other", frozenset({_PERIOD})),
        (_DEFINITION_ID, frozenset()),
    ],
)
def test_a_single_period_replay_refuses_another_admission(definition_id: str, periods: frozenset[Period]) -> None:
    context = _context(AccessAction.OBSERVE, result_schema_id="any.registered.result")
    context = replace(context, admitted_request=_admitted(context, definition_id=definition_id, periods=periods))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        bind_replayed_or_fresh_single_period_access(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            definition_id=_DEFINITION_ID,
            fresh_period=_period_must_not_be_read,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_fresh_single_period_access_needs_held_authority_before_reading() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        bind_replayed_or_fresh_single_period_access(
            _context(AccessAction.SUBMIT, result_schema_id="any.registered.result"),
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            definition_id=_DEFINITION_ID,
            fresh_period=_period_must_not_be_read,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_fresh_single_period_access_binds_the_period_read_under_held_authority() -> None:
    authority = cast(Any, object())
    read_under: list[object] = []
    other_period = Period.from_year_and_code(2026, "2T")

    def read_period(operation: object) -> Period:
        read_under.append(operation)
        return other_period

    context = replace(
        _context(AccessAction.SUBMIT, result_schema_id="any.registered.result"), authority_operation=authority
    )
    resolved = bind_replayed_or_fresh_single_period_access(
        context,
        LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
        fresh_period=read_period,
    )

    assert read_under == [authority]
    assert resolved.request.periods == frozenset({other_period})


def test_period_independent_replay_requires_a_period_independent_admission() -> None:
    context = _context(AccessAction.RESULT, result_schema_id="any.registered.result")

    replayed = bind_replayed_period_independent_access(
        replace(context, admitted_request=_admitted(context, periods=frozenset())),
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
    )
    assert replayed.request.period_independent and replayed.policy.requires_all_periods
    with pytest.raises(ProfileAccessRefusedError) as refused:
        bind_replayed_period_independent_access(
            replace(context, admitted_request=_admitted(context, periods=frozenset({_PERIOD}))),
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            definition_id=_DEFINITION_ID,
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_fresh_period_independent_access_needs_no_held_authority() -> None:
    resolved = bind_replayed_period_independent_access(
        _context(AccessAction.SUBMIT, result_schema_id="any.registered.result"),
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
    )

    assert resolved.request.period_independent and resolved.request.action is AccessAction.SUBMIT


@pytest.mark.parametrize(
    "action", [AccessAction.OBSERVE, AccessAction.RESULT, AccessAction.CANCEL, AccessAction.DETACH]
)
def test_a_replay_from_a_fresh_session_keeps_the_admitted_scope_whatever_its_origin(action: AccessAction) -> None:
    """A later session has a new destination and may use another frontend; observation stays available."""
    submitted = _context(AccessAction.SUBMIT, result_schema_id="any.registered.result")
    later = replace(
        _context(action, result_schema_id="any.registered.result"), frontend=OperationFrontendProjection.MCP
    )
    assert later.destination_id != submitted.destination_id

    single = bind_replayed_or_fresh_single_period_access(
        replace(later, admitted_request=_admitted(submitted, periods=frozenset({_PERIOD}))),
        LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
        fresh_period=_period_must_not_be_read,
    )
    independent = bind_replayed_period_independent_access(
        replace(later, admitted_request=_admitted(submitted, periods=frozenset())),
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        definition_id=_DEFINITION_ID,
    )

    assert single.request.periods == frozenset({_PERIOD})
    assert independent.request.period_independent
    for resolved in (single, independent):
        assert resolved.request.destination_id == later.destination_id
        assert resolved.request.frontend is OperationFrontendProjection.MCP
        assert all(item.destination_id == later.destination_id for item in resolved.policy.disclosures)
