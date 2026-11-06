"""Each certificate operation admits only its own request class, and only record and remove take COMMIT."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationRequest
from ...operations.registry import OperationPublicDefinitionRegistrationV1
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
)
from ..registered_operation import (
    build_retencion_soportada_list_definition,
    build_retencion_soportada_list_registration,
    build_retencion_soportada_mutation_registration,
    build_retencion_soportada_remove_definition,
    resolve_retencion_soportada_operation_access,
)
from ..requests import RetencionSoportadaListRequest, RetencionSoportadaRemoveRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unused_ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> NoReturn:
    raise AssertionError(f"unexpected operation execution for {profile_id} with {operation!r}")


def _context(registration: OperationPublicDefinitionRegistrationV1) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _request(definition_id: str, payload: BaseModel) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def _list_payload(profile_id: UUID = _PROFILE) -> RetencionSoportadaListRequest:
    return RetencionSoportadaListRequest(profile_id=profile_id, ejercicio=2024)


def _remove_payload() -> RetencionSoportadaRemoveRequest:
    return RetencionSoportadaRemoveRequest(
        profile_id=_PROFILE,
        ejercicio=2024,
        income_class=RetencionSoportadaClase.TRABAJO,
        payer_ref="a" * 64,
        expected_revision_id="rev-1",
    )


def _list_registration() -> OperationPublicDefinitionRegistrationV1:
    return build_retencion_soportada_list_registration(build_retencion_soportada_list_definition(_unused_ports))


def _remove_registration() -> OperationPublicDefinitionRegistrationV1:
    return build_retencion_soportada_mutation_registration(build_retencion_soportada_remove_definition(_unused_ports))


def test_list_is_a_whole_profile_read_without_a_commit_door() -> None:
    resolved = resolve_retencion_soportada_operation_access(
        _request(RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID, _list_payload()), _context(_list_registration())
    )

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.period_independent
    assert AccessAction.COMMIT not in resolved.policy.actions


def test_remove_is_a_whole_profile_read_with_the_commit_door() -> None:
    resolved = resolve_retencion_soportada_operation_access(
        _request(RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID, _remove_payload()),
        _context(_remove_registration()),
    )

    assert resolved.request.period_independent
    assert AccessAction.COMMIT in resolved.policy.actions


def test_a_payload_of_another_certificate_operation_is_unavailable() -> None:
    for definition_id, payload in (
        (RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID, _list_payload()),
        (RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID, _list_payload()),
        (RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID, _remove_payload()),
        ("retencion-soportada.unknown", _list_payload()),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_retencion_soportada_operation_access(
                _request(definition_id, payload), _context(_remove_registration())
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_a_payload_for_another_profile_is_a_profile_mismatch() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_retencion_soportada_operation_access(
            _request(RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID, _list_payload(_OTHER_PROFILE)),
            _context(_list_registration()),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
