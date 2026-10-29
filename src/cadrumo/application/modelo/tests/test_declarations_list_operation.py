"""The declarations list is read for exactly one profile, under whole-profile consent, each row once."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope, Availability

from ....core.external_constants import OutputLanguage
from ....core.operations import profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.operation_access_policy import operation_scope_refusal
from ..declarations_list import DeclarationListGroup, DeclarationListInputs
from ..declarations_list_operation import (
    MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
    ModeloDeclarationsListProjectionV1,
    ModeloDeclarationsListRequest,
    build_modelo_declarations_list_definition,
    build_modelo_declarations_list_registration,
)
from ..declarations_list_projection import ModeloDeclarationListRowV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unread(profile_id: str, operation: PinnedAuthorityOperation) -> Callable[[], DeclarationListInputs]:
    raise AssertionError("resolving access reads no declaration")


def _registration():
    definition = build_modelo_declarations_list_definition(_unread)
    registration = build_modelo_declarations_list_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, profile_id: UUID = _PROFILE, subject: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    request = OperationRequest[ModeloDeclarationsListRequest](
        definition_id=MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject)),
        payload=ModeloDeclarationsListRequest(profile_id=profile_id, output_language=OutputLanguage.ES),
    )
    return cast(OperationRequest[BaseModel], cast(object, request))


def _context(registration, *, frontend: OperationFrontendProjection = OperationFrontendProjection.CLI):
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_the_list_needs_consent_to_every_period_and_holds_no_commit_door() -> None:
    registry, registration = _registration()
    resolved = resolve_operation_access(registry=registry, request=_request(), context=_context(registration))

    assert resolved.request.period_independent and not resolved.request.periods
    assert resolved.policy.allow_period_independent and resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions
    one_quarter = AccessScope(
        operations=frozenset({MODELO_DECLARATIONS_LIST_OPERATION_DEFINITION_ID}),
        actions=frozenset({AccessAction.SUBMIT}),
        disclosures=frozenset(),
        periods=frozenset({Period.from_year_and_code(2026, "1T")}),
        allow_period_independent=True,
        allow_delegation=False,
    )
    denied = operation_scope_refusal(request=resolved.request, policy=resolved.policy, scope=one_quarter)
    assert denied is not None and denied.code is AccessDenialCode.PERIOD_DENIED


@pytest.mark.parametrize(("profile_id", "subject"), [(_OTHER, _OTHER), (_OTHER, _PROFILE), (_PROFILE, _OTHER)])
def test_a_list_for_another_profile_is_refused(profile_id: UUID, subject: UUID) -> None:
    registry, registration = _registration()

    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry, request=_request(profile_id=profile_id, subject=subject), context=_context(registration)
        )


def _row(key: str) -> ModeloDeclarationListRowV1:
    return ModeloDeclarationListRowV1(
        key=key,
        group=DeclarationListGroup.NOT_STARTED,
        group_words="Due, not started",
        state="not_started",
        modelo="303",
        modelo_title="Modelo 303",
        modelo_number="Modelo 303",
        state_words="Not started",
    )


def test_the_result_lists_each_row_once() -> None:
    one = ModeloDeclarationsListProjectionV1(
        result_version=1,
        profile_id=_PROFILE,
        output_language=OutputLanguage.EN,
        rows=(_row("due:a"), _row("due:b")),
        zones=(),
        sources=(),
    )
    assert ModeloDeclarationsListProjectionV1.model_validate_json(one.model_dump_json()) == one
    with pytest.raises(ValidationError):
        ModeloDeclarationsListProjectionV1(
            result_version=1,
            profile_id=_PROFILE,
            output_language=OutputLanguage.EN,
            rows=(_row("due:a"),) * 2,
            zones=(),
            sources=(),
        )
