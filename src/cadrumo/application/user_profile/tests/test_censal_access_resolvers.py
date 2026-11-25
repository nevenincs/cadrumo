"""The censal resolvers refuse another operation or payload as unavailable before the profile mismatch."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ...operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ...operations.models import OperationRequest
from ...operations.registry import OperationPublicDefinitionRegistrationV1
from ..access_errors import ProfileAccessRefusedError
from ..censal_file_import_operation import (
    CensalFileImportOperationRequest,
    build_censal_file_import_operation_definition,
    build_censal_file_import_operation_registration,
    resolve_censal_file_import_operation_access,
)
from ..censal_prepare_operation import (
    CensalPrepareOperationRequest,
    build_censal_prepare_operation_definition,
    build_censal_prepare_operation_registration,
    resolve_censal_prepare_operation_access,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

type _Resolver = Callable[[OperationRequest[BaseModel], OperationAccessContext], ResolvedOperationAccess]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


class _ForeignRequest(BaseModel):
    profile_id: UUID


def _import_registration() -> OperationPublicDefinitionRegistrationV1:
    return build_censal_file_import_operation_registration(build_censal_file_import_operation_definition())


def _prepare_registration() -> OperationPublicDefinitionRegistrationV1:
    return build_censal_prepare_operation_registration(build_censal_prepare_operation_definition())


_CASES = [
    pytest.param(
        resolve_censal_file_import_operation_access,
        _import_registration,
        "user-profile.censo-file-import",
        CensalFileImportOperationRequest,
        True,
        id="file-import",
    ),
    pytest.param(
        resolve_censal_prepare_operation_access,
        _prepare_registration,
        "user-profile.censo-prepare",
        CensalPrepareOperationRequest,
        False,
        id="prepare",
    ),
]


def _context(registration: OperationPublicDefinitionRegistrationV1) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _request(payload: BaseModel, *, definition_id: str, profile_id: UUID = _PROFILE) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel].model_construct(
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=payload,
    )


def _refusal(
    resolver: _Resolver, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> AccessDenialCode:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolver(request, context)
    return refused.value.reason


@pytest.mark.parametrize(("resolver", "registration", "definition_id", "payload_type", "commits"), _CASES)
def test_censal_resolver_admits_its_own_request_and_commits_only_the_import(
    resolver: _Resolver,
    registration: Callable[[], OperationPublicDefinitionRegistrationV1],
    definition_id: str,
    payload_type: type[BaseModel],
    commits: bool,
) -> None:
    request = _request(payload_type.model_construct(profile_id=_PROFILE), definition_id=definition_id)

    resolved = resolver(request, _context(registration()))

    assert resolved.request.profile_id == _PROFILE
    assert (AccessAction.COMMIT in resolved.policy.actions) is commits


@pytest.mark.parametrize(("resolver", "registration", "definition_id", "payload_type", "commits"), _CASES)
def test_censal_resolver_refuses_another_definition_or_payload_as_unavailable_before_the_profile(
    resolver: _Resolver,
    registration: Callable[[], OperationPublicDefinitionRegistrationV1],
    definition_id: str,
    payload_type: type[BaseModel],
    commits: bool,
) -> None:
    context = _context(registration())
    other_definition = _request(
        payload_type.model_construct(profile_id=_OTHER_PROFILE),
        definition_id="censal.other-operation",
        profile_id=_OTHER_PROFILE,
    )
    other_payload = _request(
        _ForeignRequest(profile_id=_OTHER_PROFILE), definition_id=definition_id, profile_id=_OTHER_PROFILE
    )

    assert _refusal(resolver, other_definition, context) is AccessDenialCode.OPERATION_UNAVAILABLE
    assert _refusal(resolver, other_payload, context) is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize(("resolver", "registration", "definition_id", "payload_type", "commits"), _CASES)
def test_censal_resolver_refuses_a_foreign_payload_profile_or_subject_as_a_mismatch(
    resolver: _Resolver,
    registration: Callable[[], OperationPublicDefinitionRegistrationV1],
    definition_id: str,
    payload_type: type[BaseModel],
    commits: bool,
) -> None:
    context = _context(registration())
    foreign_payload = _request(
        payload_type.model_construct(profile_id=_OTHER_PROFILE), definition_id=definition_id, profile_id=_OTHER_PROFILE
    )
    foreign_subject = _request(
        payload_type.model_construct(profile_id=_PROFILE), definition_id=definition_id, profile_id=_OTHER_PROFILE
    )

    assert _refusal(resolver, foreign_payload, context) is AccessDenialCode.PROFILE_MISMATCH
    assert _refusal(resolver, foreign_subject, context) is AccessDenialCode.PROFILE_MISMATCH
