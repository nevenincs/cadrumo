"""Every Modelo 232 related-party write is a committing whole-profile operation bound to its own request class."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability

from ....core.operations import OperationFrontendProjection, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationRequest
from ...operations.registry import OperationPublicDefinitionRegistrationV1
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..contracts import (
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_WRITE_DEFINITION_IDS,
)
from ..executor import M232_RELATED_PARTY_REQUEST_TYPES
from ..registered_operation import (
    build_m232_related_party_definition,
    build_m232_related_party_list_registration,
    build_m232_related_party_registration,
    resolve_m232_related_party_operation_access,
)
from ..requests import Modelo232NoneStateRequest, Modelo232NoneWithdrawRequest, Modelo232RelatedPartyListRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000ab")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bc")
_EJERCICIO = filing_year_envelope().horizon


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


def _state_none(profile_id: UUID = _PROFILE) -> Modelo232NoneStateRequest:
    return Modelo232NoneStateRequest(profile_id=profile_id, ejercicio=_EJERCICIO, note="No related parties.")


def _withdraw_none() -> Modelo232NoneWithdrawRequest:
    return Modelo232NoneWithdrawRequest(profile_id=_PROFILE, ejercicio=_EJERCICIO, expected_revision_id="rev-1")


def _registration(definition_id: str = M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID):
    definition = build_m232_related_party_definition(definition_id, _unused_ports)
    if definition_id == M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID:
        return build_m232_related_party_list_registration(definition)
    return build_m232_related_party_registration(definition)


def test_every_definition_admits_one_request_class_and_only_writes_commit() -> None:
    assert set(M232_RELATED_PARTY_REQUEST_TYPES) == {
        *M232_RELATED_PARTY_WRITE_DEFINITION_IDS,
        M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    }
    assert len(set(M232_RELATED_PARTY_REQUEST_TYPES.values())) == len(M232_RELATED_PARTY_REQUEST_TYPES)


def test_the_none_writes_are_whole_profile_operations_with_the_commit_door() -> None:
    for definition_id, payload in (
        (M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID, _state_none()),
        (M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID, _withdraw_none()),
    ):
        resolved = resolve_m232_related_party_operation_access(
            _request(definition_id, payload), _context(_registration(definition_id))
        )

        assert resolved.request.period_independent
        assert AccessAction.COMMIT in resolved.policy.actions


def test_the_listing_is_a_whole_profile_read_without_the_commit_door() -> None:
    resolved = resolve_m232_related_party_operation_access(
        _request(
            M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
            Modelo232RelatedPartyListRequest(profile_id=_PROFILE, ejercicio=_EJERCICIO),
        ),
        _context(_registration(M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID)),
    )

    assert resolved.request.period_independent
    assert AccessAction.COMMIT not in resolved.policy.actions


def test_a_payload_of_another_operation_or_an_unknown_definition_is_unavailable() -> None:
    for definition_id, payload in (
        (M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID, _withdraw_none()),
        (M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID, _state_none()),
        ("ledger.operaciones_vinculadas.unknown", _state_none()),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_m232_related_party_operation_access(_request(definition_id, payload), _context(_registration()))
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_a_payload_for_another_profile_is_a_profile_mismatch() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_m232_related_party_operation_access(
            _request(M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID, _state_none(_OTHER_PROFILE)),
            _context(_registration()),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
