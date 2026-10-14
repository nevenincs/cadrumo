"""A stored document is read under the same access whichever of the person's frontends asks for the read.

The registered resolver is asked for the read that stays on this machine and
for the read that sends the document to a hosted model, at every access a
session can ask for. The read that stays here is granted the same policy on
every frontend. The consent to an off-host read is the person's own act: it
travels in the request, in the same fields on every frontend the person uses,
and the automation's frontend is refused it.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.config_support import LLMProvider
from ....core.operations import profile_operation_subject
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessPolicy
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import invoice_evidence_extract_operation as extract_operation
from .. import invoice_evidence_operation as operation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_SOURCE = "a" * 64
_EVIDENCE = "e" * 16
_DEFINITION_ID = extract_operation.LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID
_ACCESSES = [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT]


def _unopened_ports(**_kwargs: object) -> operation_ports.InvoiceEvidenceOperationPorts:
    raise AssertionError("access resolution opened the evidence ports")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = extract_operation.build_ledger_evidence_extract_definition(_unopened_ports)
    registration = extract_operation.build_ledger_evidence_extract_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _request(*, off_host: bool) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=extract_operation.LedgerEvidenceExtractRequest(
            profile_id=_PROFILE,
            evidence_id=_EVIDENCE if off_host else None,
            attachment_id=None if off_host else _SOURCE,
            off_host_provider=LLMProvider.ANTHROPIC if off_host else None,
            acknowledge_off_host=off_host,
        ),
    )


def _granted(*, off_host: bool, frontend: OperationFrontendProjection, action: AccessAction) -> OperationAccessPolicy:
    registry, registration = _registry()
    resolved = resolve_operation_access(
        registry=registry,
        request=_request(off_host=off_host),
        context=OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=_SESSION_CLIENT,
            action=action,
            frontend=frontend,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        ),
    )
    assert resolved.request.frontend is frontend
    return resolved.policy


_PERSONS_FRONTENDS = [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI]
"""The person's frontends, written out rather than read from the predicate under test."""


@pytest.mark.parametrize("action", _ACCESSES)
@pytest.mark.parametrize("off_host", [False, True], ids=["on-host", "off-host"])
def test_a_read_is_granted_the_same_policy_on_every_frontend_that_may_ask_for_it(
    off_host: bool, action: AccessAction
) -> None:
    frontends = _PERSONS_FRONTENDS if off_host else list(OperationFrontendProjection)
    policies = {frontend: _granted(off_host=off_host, frontend=frontend, action=action) for frontend in frontends}

    assert len(policies) == len(frontends) > 1
    assert len(set(policies.values())) == 1
    for policy in policies.values():
        assert policy.requires_human is False
        # Sending a document off the machine is a write to the consent ledger, so it sits
        # behind the commit door for every caller; the read that stays here does not.
        assert (AccessAction.COMMIT in policy.actions) is off_host


@pytest.mark.parametrize(
    "frontend",
    [OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.INSTALLED_SERVICE],
    ids=lambda item: item.value,
)
@pytest.mark.parametrize("action", _ACCESSES)
def test_each_automation_frontend_is_refused_the_consent_to_an_off_host_read(
    action: AccessAction, frontend: OperationFrontendProjection
) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        _granted(off_host=True, frontend=frontend, action=action)
    assert refused.value.reason == AccessDenialCode.PERSON_ACT_REQUIRED.value
