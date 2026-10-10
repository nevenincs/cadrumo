"""Registered profile maintenance resolves one exact, period-independent access policy."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
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
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
    ProfileBundleExportOperationRequest,
    ProfileFieldMutationOperationRequest,
    ProfilePatchOperationRequest,
    ProfilePatchValue,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewOperationRequest,
    ProfileViewPageKind,
)
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.core.capabilities import ServiceCapability
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from .foreign_operation_payload import ForeignProfilePayload

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
_COMMITTING_ROUTES = frozenset({"field_mutation", "bundle_export"})
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
def test_registered_profile_route_binds_period_independent_access_and_commits_only_to_change_or_export(
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
    assert (AccessAction.COMMIT in policy.actions) is (route in _COMMITTING_ROUTES)
    assert policy.actions | {AccessAction.COMMIT} == frozenset(_ALL_ACTIONS)
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
        payload=ForeignProfilePayload(profile_id=_OTHER_PROFILE),
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


_CAPABILITY_PATHS = tuple(capability.schema_path for capability in ServiceCapability)
_CAPABILITY_ADDRESSES = (
    *_CAPABILITY_PATHS,
    # The fact writer trims the path, so a padded one stores the same capability.
    f"  {ServiceCapability.CLOUD_EVIDENCE_UPLOAD.schema_path}\t",
    # A member the capability enum does not name yet still lies in the section.
    "capabilities.later_service",
)
_OTHER_FIELD_PATHS = (
    "preferences.output_language",
    "identity.notes",
    # A section that only begins with the same letters is not the capability section.
    "capabilities_note.text",
)


def _field_mutation(path: str, value: str) -> OperationRequest[BaseModel]:
    return OperationRequest(
        definition_id=PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{_PROFILE}",
        payload=ProfileFieldMutationOperationRequest(
            profile_id=_PROFILE,
            expected_revision=1,
            expected_content_digest="0" * 64,
            path=path,
            value=value,
        ),
    )


def _resolve_on(
    frontend: OperationFrontendProjection, request: OperationRequest[BaseModel], action: AccessAction
) -> ResolvedOperationAccess:
    registry = _registry()
    context = replace(_context(registry, request, action), frontend=frontend)
    return resolve_operation_access(registry=registry, request=request, context=context)


def test_the_capability_cases_name_every_service_capability() -> None:
    assert _CAPABILITY_PATHS
    assert set(_CAPABILITY_PATHS) < set(_CAPABILITY_ADDRESSES)


@pytest.mark.parametrize("value", ["true", "false", ""])
@pytest.mark.parametrize("action", _ALL_ACTIONS)
@pytest.mark.parametrize("path", _CAPABILITY_ADDRESSES)
def test_an_mcp_client_is_refused_setting_or_clearing_a_service_capability(
    path: str, action: AccessAction, value: str
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        _resolve_on(OperationFrontendProjection.MCP, _field_mutation(path, value), action)

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
@pytest.mark.parametrize("value", ["true", "false", ""])
@pytest.mark.parametrize("path", _CAPABILITY_ADDRESSES)
def test_a_persons_frontend_still_sets_and_clears_a_service_capability(
    path: str, value: str, frontend: OperationFrontendProjection
) -> None:
    resolved = _resolve_on(frontend, _field_mutation(path, value), AccessAction.SUBMIT)

    assert resolved.request.frontend is frontend
    assert AccessAction.COMMIT in resolved.policy.actions


@pytest.mark.parametrize("action", _ALL_ACTIONS)
@pytest.mark.parametrize("path", _OTHER_FIELD_PATHS)
def test_an_mcp_client_still_changes_every_field_that_is_not_a_service_capability(
    path: str, action: AccessAction
) -> None:
    request = _field_mutation(path, "es")

    on_mcp = _resolve_on(OperationFrontendProjection.MCP, request, action)

    assert on_mcp.request.frontend is OperationFrontendProjection.MCP
    assert on_mcp.request.action is action
    assert on_mcp.policy == _resolve_on(OperationFrontendProjection.CLI, request, action).policy
    assert AccessAction.COMMIT in on_mcp.policy.actions


_KNOWN_CAPABILITY_QUESTIONS = ("llm-vision", "google-export")
"""The capability questions the setup catalogue asks today, named here independently of it."""
_OTHER_QUESTION = "notes"


def _patch(*answers: tuple[str, str], colegio_concertado: bool | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest(
        definition_id=PROFILE_PATCH_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{_PROFILE}",
        payload=ProfilePatchOperationRequest(
            profile_id=_PROFILE,
            expected_revision=1,
            expected_content_digest="0" * 64,
            values=tuple(ProfilePatchValue(question_id=question_id, value=value) for question_id, value in answers),
            colegio_concertado=colegio_concertado,
        ),
    )


def _resolve_patch(
    frontend: OperationFrontendProjection,
    request: OperationRequest[BaseModel],
    action: AccessAction,
    operation: PinnedAuthorityOperation | None,
) -> ResolvedOperationAccess:
    """Ask the registered resolver as the host does, with or without its pinned authority."""
    registry = _registry()
    context = replace(_context(registry, request, action), frontend=frontend, authority_operation=operation)
    return resolve_operation_access(registry=registry, request=request, context=context)


def _catalogue_capability_questions(operation: PinnedAuthorityOperation) -> set[str]:
    return {
        question.id
        for section in build_setup_flow(operation).sections
        for question in section.questions
        if question.profile_key is not None and question.profile_key.split(".")[0] == "capabilities"
    }


def test_the_setup_catalogue_asks_the_known_capability_questions(operation: PinnedAuthorityOperation) -> None:
    asked = _catalogue_capability_questions(operation)

    assert set(_KNOWN_CAPABILITY_QUESTIONS) <= asked
    questions = {
        question.id: question.profile_key
        for section in build_setup_flow(operation).sections
        for question in section.questions
    }
    assert {questions[question_id] for question_id in asked} <= {item.schema_path for item in ServiceCapability}
    assert questions[_OTHER_QUESTION] == "identity.notes"


@pytest.mark.parametrize("value", ["true", "false", ""])
@pytest.mark.parametrize("action", _ALL_ACTIONS)
@pytest.mark.parametrize("question_id", _KNOWN_CAPABILITY_QUESTIONS)
def test_an_mcp_client_is_refused_a_patch_that_answers_a_capability_question(
    question_id: str, action: AccessAction, value: str, operation: PinnedAuthorityOperation
) -> None:
    alone = _patch((question_id, value))
    among_others = _patch((_OTHER_QUESTION, "synthetic note"), (question_id, value))

    for request in (alone, among_others):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            _resolve_patch(OperationFrontendProjection.MCP, request, action, operation)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def test_every_capability_question_the_catalogue_asks_is_refused_to_mcp(operation: PinnedAuthorityOperation) -> None:
    """The refusal follows the catalogue, so a capability question added later is covered."""
    asked = sorted(_catalogue_capability_questions(operation))
    assert asked

    for question_id in asked:
        request = _patch((question_id, "false"))
        with pytest.raises(ProfileAccessRefusedError) as refused:
            _resolve_patch(OperationFrontendProjection.MCP, request, AccessAction.SUBMIT, operation)
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED, question_id


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
@pytest.mark.parametrize("with_authority", [True, False])
@pytest.mark.parametrize("question_id", _KNOWN_CAPABILITY_QUESTIONS)
def test_a_persons_frontend_still_patches_a_capability_answer(
    question_id: str, with_authority: bool, frontend: OperationFrontendProjection, operation: PinnedAuthorityOperation
) -> None:
    request = _patch((question_id, "false"))

    resolved = _resolve_patch(frontend, request, AccessAction.SUBMIT, operation if with_authority else None)

    assert resolved.request.frontend is frontend
    assert AccessAction.COMMIT in resolved.policy.actions


@pytest.mark.parametrize("action", _ALL_ACTIONS)
def test_an_mcp_client_still_patches_answers_that_touch_no_capability(
    action: AccessAction, operation: PinnedAuthorityOperation
) -> None:
    request = _patch((_OTHER_QUESTION, "synthetic note"), colegio_concertado=True)

    on_mcp = _resolve_patch(OperationFrontendProjection.MCP, request, action, operation)

    assert on_mcp.request.frontend is OperationFrontendProjection.MCP
    assert on_mcp.policy == _resolve_patch(OperationFrontendProjection.CLI, request, action, operation).policy
    assert AccessAction.COMMIT in on_mcp.policy.actions


def test_a_patch_that_answers_no_question_needs_no_catalogue_on_mcp() -> None:
    request = _patch(colegio_concertado=False)

    resolved = _resolve_patch(OperationFrontendProjection.MCP, request, AccessAction.SUBMIT, None)

    assert resolved.request.frontend is OperationFrontendProjection.MCP


def test_an_mcp_patch_with_answers_is_refused_when_the_catalogue_cannot_be_read() -> None:
    """Without the pinned authority no answer can be shown to leave the capabilities alone."""
    with pytest.raises(ProfileAccessRefusedError) as refused:
        _resolve_patch(
            OperationFrontendProjection.MCP, _patch((_OTHER_QUESTION, "synthetic note")), AccessAction.SUBMIT, None
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
