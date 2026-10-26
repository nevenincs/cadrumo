"""The local-reader operations resolve to one access whichever frontend submits them."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, DisclosureCategory

from ...core.operations import profile_operation_subject
from ..local_reader_contracts import LOCAL_READER_OPERATION_SUBJECT
from ..local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportRequest,
    build_local_reader_report_definition,
    build_local_reader_report_registration,
)
from ..local_reader_status_operation import (
    LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
    LocalReaderStatusRequest,
    build_local_reader_status_definition,
    build_local_reader_status_registration,
)
from ..modelo.tests.m036_operation_support import PROFILE_ID, policy_decision
from ..operations.access_resolution import OperationAccessContext, resolve_operation_access
from ..operations.models import OperationRequest
from ..operations.registry import OperationFrontendProjection, OperationRegistry
from ..user_profile.access_errors import ProfileAccessRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000bb")


@dataclass(frozen=True, slots=True)
class _Case:
    """One read of the local-reader family."""

    definition_id: str
    subject_ref: str
    payload: BaseModel


_CASES = {
    "status": _Case(
        LOCAL_READER_STATUS_OPERATION_DEFINITION_ID, LOCAL_READER_OPERATION_SUBJECT, LocalReaderStatusRequest()
    ),
    "report": _Case(
        LOCAL_READER_REPORT_OPERATION_DEFINITION_ID, LOCAL_READER_OPERATION_SUBJECT, LocalReaderReportRequest()
    ),
}


def _registry() -> OperationRegistry:
    status = build_local_reader_status_definition()
    report = build_local_reader_report_definition()
    return OperationRegistry(
        definitions=(report, status),
        public_registrations=(
            build_local_reader_report_registration(report),
            build_local_reader_status_registration(status),
        ),
    )


def _request(case: _Case, *, subject_ref: str | None = None) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=case.definition_id,
        subject_ref=case.subject_ref if subject_ref is None else subject_ref,
        payload=case.payload,
    )


def _context(
    registry: OperationRegistry, case: _Case, action: AccessAction = AccessAction.SUBMIT
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=_DESTINATION,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(case.definition_id),
        published_authority=Availability.AVAILABLE,
    )


def test_the_cases_cover_every_operation_of_the_family() -> None:
    assert {case.definition_id for case in _CASES.values()} == {
        contract.definition_id for contract in _registry().public_contract_set.definitions
    }


@pytest.mark.parametrize("access", [AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT])
@pytest.mark.parametrize("name", sorted(_CASES))
def test_every_frontend_resolves_each_request_to_the_same_period_independent_access(
    name: str, access: AccessAction
) -> None:
    case = _CASES[name]
    registry = _registry()
    context = _context(registry, case, access)
    on_cli = resolve_operation_access(registry=registry, request=_request(case), context=context)

    assert on_cli.request.period_independent and not on_cli.request.periods
    assert not on_cli.policy.requires_human and not on_cli.policy.requires_all_periods
    assert AccessAction.COMMIT not in on_cli.policy.actions
    for frontend in OperationFrontendProjection:
        on_frontend = resolve_operation_access(
            registry=registry, request=_request(case), context=replace(context, frontend=frontend)
        )
        assert on_frontend.policy == on_cli.policy, frontend
        assert on_frontend.request == on_cli.request.model_copy(update={"frontend": frontend}), frontend


@pytest.mark.parametrize("name", sorted(_CASES))
def test_a_scope_that_holds_no_commit_submits_every_read(
    name: str,
) -> None:
    case = _CASES[name]
    registry = _registry()
    resolved = resolve_operation_access(registry=registry, request=_request(case), context=_context(registry, case))

    decision = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)

    assert isinstance(decision, AccessAllowed)


@pytest.mark.parametrize("name", ["status", "report"])
def test_the_result_discloses_profile_values_to_the_requesting_destination_alone(name: str) -> None:
    case = _CASES[name]
    registry = _registry()
    resolved = resolve_operation_access(
        registry=registry, request=_request(case), context=_context(registry, case, AccessAction.RESULT)
    )

    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert {item.destination_id for item in resolved.policy.disclosures} == {_DESTINATION}


@pytest.mark.parametrize("name", ["status", "report"])
@pytest.mark.parametrize(
    "subject_ref",
    [profile_operation_subject(str(PROFILE_ID)), str(PROFILE_ID), "9b0c2f4e-5a1d-4c3b-8e7f-0a1b2c3d4e5f"],
)
def test_a_subject_other_than_the_machines_own_is_refused(name: str, subject_ref: str) -> None:
    case = _CASES[name]
    registry = _registry()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry, request=_request(case, subject_ref=subject_ref), context=_context(registry, case)
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
