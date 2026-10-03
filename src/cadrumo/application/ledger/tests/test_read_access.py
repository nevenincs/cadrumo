"""Ledger read access binds exact-profile scope; commit access only adds the COMMIT door."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..action_ports import LedgerActionPorts
from ..read_access import resolve_ledger_commit_access, resolve_ledger_read_access, resolve_ledger_request_read_access
from ..remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveRequest,
    build_ledger_remove_definition,
    build_ledger_remove_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


def _unused_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    raise AssertionError(f"unexpected operation execution for {bucket_id} with {operation!r}")


def _registration() -> OperationPublicDefinitionRegistrationV1:
    return build_ledger_remove_registration(build_ledger_remove_definition(_unused_ports))


def _request(
    payload: BaseModel, *, definition_id: str = LEDGER_REMOVE_OPERATION_DEFINITION_ID
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def _remove_payload() -> LedgerRemoveRequest:
    return LedgerRemoveRequest(profile_id=_PROFILE, transaction_id="a" * 64)


def _context(registration: OperationPublicDefinitionRegistrationV1) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_commit_access_adds_only_the_commit_action_to_the_read_policy() -> None:
    registration = _registration()
    request = _request(_remove_payload())
    context = _context(registration)

    read = resolve_ledger_read_access(request, context, profile_id=_PROFILE, periods=frozenset())
    commit = resolve_ledger_commit_access(request, context, profile_id=_PROFILE, periods=frozenset())

    assert AccessAction.COMMIT not in read.policy.actions
    assert commit.policy.actions == read.policy.actions | {AccessAction.COMMIT}
    assert commit.request == read.request
    assert commit.policy.model_dump(exclude={"actions"}) == read.policy.model_dump(exclude={"actions"})


def test_commit_access_keeps_the_read_refusal_for_a_foreign_profile() -> None:
    registration = _registration()
    request = _request(_remove_payload())

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_ledger_commit_access(request, _context(registration), profile_id=_OTHER_PROFILE, periods=frozenset())

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_request_read_access_binds_the_payload_profile_for_the_exact_request_type() -> None:
    registration = _registration()
    request = _request(_remove_payload())
    context = _context(registration)

    resolved = resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_REMOVE_OPERATION_DEFINITION_ID,
        request_type=LedgerRemoveRequest,
    )

    assert resolved == resolve_ledger_read_access(request, context, profile_id=_PROFILE, periods=frozenset())


class _RemoveRequestSubclass(LedgerRemoveRequest):
    """A payload that is-a removal request but is not the registered request type."""


@pytest.mark.parametrize(
    "request_factory",
    (
        lambda: _request(_remove_payload(), definition_id="ledger.reset"),
        lambda: _request(_RemoveRequestSubclass(profile_id=_PROFILE, transaction_id="a" * 64)),
    ),
    ids=("other-definition", "subclass-payload"),
)
def test_request_read_access_refuses_anything_but_the_exact_definition_and_type(
    request_factory: Callable[[], OperationRequest[BaseModel]],
) -> None:
    registration = _registration()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_ledger_request_read_access(
            request_factory(),
            _context(registration),
            definition_id=LEDGER_REMOVE_OPERATION_DEFINITION_ID,
            request_type=LedgerRemoveRequest,
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
