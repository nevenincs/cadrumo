"""Registered profile maintenance resolves one exact, period-independent access policy."""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OperationAccessContext,
    resolve_operation_access,
)
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_access import (
    resolve_profile_bundle_export_access,
    resolve_profile_mutation_access,
    resolve_profile_view_access,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileBundleExportOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfileLogoutOperationRequest,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.core.period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000b1")
_OTHER_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000b2")
_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000b3")
_ALL_ACTIONS = (
    AccessAction.SUBMIT,
    AccessAction.START,
    AccessAction.RESUME,
    AccessAction.COMMIT,
    AccessAction.CANCEL,
    AccessAction.DETACH,
    AccessAction.OBSERVE,
    AccessAction.RESULT,
)
_ROUTES = ("view", "field_mutation", "bundle_export")
_RESOLVERS = {
    "view": resolve_profile_view_access,
    "field_mutation": resolve_profile_mutation_access,
    "bundle_export": resolve_profile_bundle_export_access,
}


def _registry() -> OperationRegistry:
    return OperationRegistry(
        definitions=USER_PROFILE_OPERATION_DEFINITIONS,
        public_registrations=build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
    )


def _request(route: str, profile_id: UUID = _PROFILE, *, subject: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    payload: BaseModel
    if route == "view":
        definition_id = PROFILE_VIEW_OPERATION_DEFINITION_ID
        payload = ProfileViewOperationRequest(profile_id=profile_id, page_kind=ProfileViewPageKind.FACTS)
    elif route == "field_mutation":
        definition_id = PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
        payload = ProfileFieldMutationOperationRequest(
            profile_id=profile_id,
            expected_revision=1,
            expected_content_digest="0" * 64,
            path="preferences.output_language",
            value="es",
        )
    else:
        definition_id = PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
        payload = ProfileBundleExportOperationRequest(
            profile_id=profile_id,
            destination=Path(tempfile.gettempdir()).resolve() / "private.bundle",
            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        )
    return OperationRequest(definition_id=definition_id, subject_ref=f"profile:{subject}", payload=payload)


def _context(
    registry: OperationRegistry, request: OperationRequest[BaseModel], action: AccessAction
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=_DESTINATION,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize("action", _ALL_ACTIONS)
@pytest.mark.parametrize("route", _ROUTES)
def test_registered_profile_route_binds_committing_period_independent_profile_access(
    route: str, action: AccessAction
) -> None:
    registry = _registry()
    request = _request(route)
    context = _context(registry, request, action)

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.action is action
    assert resolved.request.period_independent and resolved.request.periods == frozenset()
    policy = resolved.policy
    assert policy.actions == frozenset(_ALL_ACTIONS)
    assert policy.periods == frozenset() and policy.allow_period_independent
    assert not policy.requires_all_periods and not policy.requires_human
    assert policy.provider is Availability.NOT_REQUIRED and policy.backend is Availability.AVAILABLE
    assert not policy.transaction_authority_required
    disclosed = {(item.destination_id, item.projection_id, item.category) for item in policy.disclosures}
    if action is AccessAction.RESULT:
        assert disclosed == {(_DESTINATION, request.definition_id + ".result", DisclosureCategory.PROFILE_VALUES)}
    elif action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        assert disclosed == {(_DESTINATION, OPERATION_OBSERVATION_PROJECTION_ID, DisclosureCategory.OPERATION_METADATA)}
    else:
        assert disclosed == set()


@pytest.mark.parametrize("route", _ROUTES)
def test_result_without_a_registered_result_schema_is_refused_not_silently_undisclosed(route: str) -> None:
    registry = _registry()
    request = _request(route)
    resolver = _RESOLVERS[route]

    def schemaless(action: AccessAction) -> OperationAccessContext:
        context = _context(registry, request, action)
        return OperationAccessContext(
            profile_id=context.profile_id,
            destination_id=context.destination_id,
            action=context.action,
            frontend=context.frontend,
            contract=context.contract.model_copy(update={"result_schema": None}),
            published_authority=context.published_authority,
        )

    assert resolver(request, schemaless(AccessAction.SUBMIT)).policy.disclosures == frozenset()
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolver(request, schemaless(AccessAction.RESULT))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("route", _ROUTES)
def test_profile_route_refuses_foreign_payload_before_profile_identity(route: str) -> None:
    registry = _registry()
    request = _request(route)
    resolver = _RESOLVERS[route]
    foreign = OperationRequest(
        definition_id=request.definition_id,
        subject_ref=f"profile:{_OTHER_PROFILE}",
        payload=ProfileLogoutOperationRequest(profile_id=_OTHER_PROFILE),
    )

    with pytest.raises(ProfileAccessRefusedError) as unavailable:
        resolver(foreign, _context(registry, request, AccessAction.SUBMIT))
    assert unavailable.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE

    for mismatched in (
        _request(route, _OTHER_PROFILE, subject=_OTHER_PROFILE),
        _request(route, subject=_OTHER_PROFILE),
    ):
        with pytest.raises(ProfileAccessRefusedError) as mismatch:
            resolver(mismatched, _context(registry, request, AccessAction.RESULT))
        assert mismatch.value.reason is AccessDenialCode.PROFILE_MISMATCH


def _admitted(registry: OperationRegistry, request: OperationRequest[BaseModel]) -> OperationAccessRequest:
    """Return the access request the real resolver admitted for this submission."""
    return resolve_operation_access(
        registry=registry, request=request, context=_context(registry, request, AccessAction.SUBMIT)
    ).request


def _replay(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
    action: AccessAction,
    admitted: OperationAccessRequest,
    *,
    destination_id: UUID = _DESTINATION,
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=destination_id,
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


def _changed(admitted: OperationAccessRequest, **update: object) -> OperationAccessRequest:
    return OperationAccessRequest.model_validate({**dict(admitted), **update})


@pytest.mark.parametrize("action", sorted(ADMISSION_REPLAY_ACTIONS))
@pytest.mark.parametrize("route", _ROUTES)
def test_same_origin_replay_of_the_admitted_submission_is_bound(route: str, action: AccessAction) -> None:
    registry = _registry()
    request = _request(route)
    fresh = resolve_operation_access(registry=registry, request=request, context=_context(registry, request, action))

    replayed = resolve_operation_access(
        registry=registry, request=request, context=_replay(registry, request, action, _admitted(registry, request))
    )

    assert replayed == fresh


@pytest.mark.parametrize("action", sorted(ADMISSION_REPLAY_ACTIONS))
@pytest.mark.parametrize("route", _ROUTES)
def test_replay_from_another_destination_and_frontend_discloses_only_to_the_caller(
    route: str, action: AccessAction
) -> None:
    """Observation is caller-independent; the caller's own disclosure scope still governs output."""
    registry = _registry()
    request = _request(route)
    caller = UUID("5aa00000-0000-4000-8000-0000000000b4")

    replayed = resolve_operation_access(
        registry=registry,
        request=request,
        context=_replay(
            registry,
            request,
            action,
            _admitted(registry, request),
            destination_id=caller,
            frontend=OperationFrontendProjection.TUI,
        ),
    )

    assert replayed.request.destination_id == caller
    assert replayed.request.frontend is OperationFrontendProjection.TUI
    assert replayed.policy.disclosures
    assert {item.destination_id for item in replayed.policy.disclosures} == {caller}


_ADMITTED_MISMATCHES = ("profile", "definition", "action", "periods")


@pytest.mark.parametrize("mismatch", _ADMITTED_MISMATCHES)
@pytest.mark.parametrize("action", sorted(ADMISSION_REPLAY_ACTIONS))
@pytest.mark.parametrize("route", _ROUTES)
def test_replay_refuses_an_admission_that_is_not_this_profiles_period_independent_submission(
    route: str, action: AccessAction, mismatch: str
) -> None:
    registry = _registry()
    request = _request(route)
    admitted = _admitted(registry, request)
    other_definition = next(item for item in _ROUTES if item != route)
    changed = {
        "profile": {"profile_id": _OTHER_PROFILE},
        "definition": {"definition_id": _request(other_definition).definition_id},
        "action": {"action": AccessAction.START},
        "periods": {"periods": frozenset({Period.from_year_and_code(2026, "1T")}), "period_independent": False},
    }[mismatch]

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=request,
            context=_replay(registry, request, action, _changed(admitted, **changed)),
        )
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("route", _ROUTES)
def test_profile_mismatch_precedes_a_mismatched_replay(route: str) -> None:
    registry = _registry()
    request = _request(route)
    foreign_admission = _changed(_admitted(registry, request), profile_id=_OTHER_PROFILE)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _RESOLVERS[route](
            _request(route, subject=_OTHER_PROFILE),
            _replay(registry, request, AccessAction.RESULT, foreign_admission),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
