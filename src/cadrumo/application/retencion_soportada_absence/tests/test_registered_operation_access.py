"""Both absence operations are committing whole-profile writes bound to their own request class."""

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
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationRequest
from ...operations.registry import OperationPublicDefinitionRegistrationV1
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ..registered_operation import (
    build_retencion_soportada_absence_attest_definition,
    build_retencion_soportada_absence_registration,
    build_retencion_soportada_absence_withdraw_definition,
    resolve_retencion_soportada_absence_operation_access,
)
from ..requests import RetencionSoportadaAbsenceAttestRequest, RetencionSoportadaAbsenceWithdrawRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon

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


def _attest(profile_id: UUID = _PROFILE) -> RetencionSoportadaAbsenceAttestRequest:
    return RetencionSoportadaAbsenceAttestRequest(
        profile_id=profile_id, ejercicio=_YEAR, income_class=RetencionSoportadaClase.TRABAJO, note="No payer withheld."
    )


def _withdraw() -> RetencionSoportadaAbsenceWithdrawRequest:
    return RetencionSoportadaAbsenceWithdrawRequest(
        profile_id=_PROFILE,
        ejercicio=_YEAR,
        income_class=RetencionSoportadaClase.TRABAJO,
        expected_revision_id="rev-1",
    )


def _registration() -> OperationPublicDefinitionRegistrationV1:
    return build_retencion_soportada_absence_registration(
        build_retencion_soportada_absence_attest_definition(_unused_ports)
    )


def test_attest_and_withdraw_are_whole_profile_reads_with_the_commit_door() -> None:
    for definition_id, payload in (
        (RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID, _attest()),
        (RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID, _withdraw()),
    ):
        registration = build_retencion_soportada_absence_registration(
            build_retencion_soportada_absence_attest_definition(_unused_ports)
            if definition_id == RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID
            else build_retencion_soportada_absence_withdraw_definition(_unused_ports)
        )

        resolved = resolve_retencion_soportada_absence_operation_access(
            _request(definition_id, payload), _context(registration)
        )

        assert resolved.request.period_independent
        assert AccessAction.COMMIT in resolved.policy.actions


def test_a_payload_of_the_other_absence_operation_or_an_unknown_definition_is_unavailable() -> None:
    for definition_id, payload in (
        (RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID, _withdraw()),
        (RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID, _attest()),
        ("ledger.retencion_soportada.absence.unknown", _attest()),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_retencion_soportada_absence_operation_access(
                _request(definition_id, payload), _context(_registration())
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_a_payload_for_another_profile_is_a_profile_mismatch() -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_retencion_soportada_absence_operation_access(
            _request(RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID, _attest(_OTHER_PROFILE)),
            _context(_registration()),
        )

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
