"""The local-reader provisioning operation resolves to one access whichever frontend submits it."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...core.config import Settings
from ...core.model_catalogue import ModelRole
from ...core.operations import profile_operation_subject
from ..local_reader import RoleFitnessOutcome
from ..local_reader_contracts import (
    LOCAL_READER_OPERATION_DEFINITION_ID,
    LOCAL_READER_OPERATION_SUBJECT,
    LocalReaderProvisionAction,
    LocalReaderProvisionRequest,
)
from ..local_reader_operation import (
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from ..modelo.tests.m036_operation_support import PROFILE_ID, policy_decision
from ..operations.access_resolution import OperationAccessContext, resolve_operation_access
from ..operations.models import OperationRequest
from ..operations.registry import OperationFrontendProjection, OperationRegistry
from ..provisioning_host import RuntimeInstaller
from ..user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ..user_profile.access_errors import ProfileAccessRefusedError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DESTINATION = UUID("5aa00000-0000-4000-8000-0000000000bb")
_REQUESTS = {
    LocalReaderProvisionAction.INSTALL: LocalReaderProvisionRequest(
        action=LocalReaderProvisionAction.INSTALL, consent=True
    ),
    LocalReaderProvisionAction.START: LocalReaderProvisionRequest(action=LocalReaderProvisionAction.START),
    LocalReaderProvisionAction.PULL: LocalReaderProvisionRequest(action=LocalReaderProvisionAction.PULL),
    LocalReaderProvisionAction.LOAD: LocalReaderProvisionRequest(
        action=LocalReaderProvisionAction.LOAD, role=ModelRole.TEXT_EXTRACTION
    ),
    LocalReaderProvisionAction.VERIFY: LocalReaderProvisionRequest(
        action=LocalReaderProvisionAction.VERIFY, role=ModelRole.TEXT_EXTRACTION
    ),
    LocalReaderProvisionAction.REMOVE: LocalReaderProvisionRequest(
        action=LocalReaderProvisionAction.REMOVE, role=ModelRole.TEXT_EXTRACTION
    ),
    LocalReaderProvisionAction.SETUP: LocalReaderProvisionRequest(
        action=LocalReaderProvisionAction.SETUP, consent=True
    ),
}


def _spawn(executable: Path, environment: object) -> int:
    raise AssertionError(f"access resolution started {executable} with {environment}")


def _install(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    raise AssertionError(f"access resolution ran {installer} for {executable} within {timeout_s}")


def _probe(model: str, settings: Settings) -> RoleFitnessOutcome:
    raise AssertionError(f"access resolution probed {model} under {settings}")


def _registry() -> OperationRegistry:
    definition = build_local_reader_operation_definition(spawn=_spawn, run_installer=_install, text_probe=_probe)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(build_local_reader_operation_registration(definition),)
    )


def _request(action: LocalReaderProvisionAction, *, subject_ref: str = LOCAL_READER_OPERATION_SUBJECT):
    return OperationRequest[BaseModel](
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID, subject_ref=subject_ref, payload=_REQUESTS[action]
    )


def _context(registry: OperationRegistry, action: AccessAction = AccessAction.SUBMIT) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=_DESTINATION,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registry.lookup_public_contract(LOCAL_READER_OPERATION_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
    )


def test_the_cases_cover_every_provisioning_action() -> None:
    assert set(_REQUESTS) == set(LocalReaderProvisionAction)


@pytest.mark.parametrize("access", [AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT])
@pytest.mark.parametrize("action", sorted(LocalReaderProvisionAction))
def test_every_frontend_resolves_each_action_to_the_same_period_independent_access(
    action: LocalReaderProvisionAction, access: AccessAction
) -> None:
    registry = _registry()
    context = _context(registry, access)
    on_cli = resolve_operation_access(registry=registry, request=_request(action), context=context)

    assert on_cli.request.period_independent and not on_cli.request.periods
    assert not on_cli.policy.requires_human and not on_cli.policy.requires_all_periods
    assert (AccessAction.COMMIT in on_cli.policy.actions) is (action is not LocalReaderProvisionAction.VERIFY)
    for frontend in OperationFrontendProjection:
        on_frontend = resolve_operation_access(
            registry=registry, request=_request(action), context=replace(context, frontend=frontend)
        )
        assert on_frontend.policy == on_cli.policy, frontend
        assert on_frontend.request == on_cli.request.model_copy(update={"frontend": frontend}), frontend


@pytest.mark.parametrize("action", sorted(LocalReaderProvisionAction))
def test_a_scope_that_holds_no_commit_submits_a_verification_and_no_other_action(
    action: LocalReaderProvisionAction,
) -> None:
    registry = _registry()
    resolved = resolve_operation_access(registry=registry, request=_request(action), context=_context(registry))

    decision = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)

    if action is LocalReaderProvisionAction.VERIFY:
        assert isinstance(decision, AccessAllowed)
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.OPERATION_DENIED


def test_the_result_discloses_profile_values_to_the_requesting_destination_alone() -> None:
    registry = _registry()
    resolved = resolve_operation_access(
        registry=registry,
        request=_request(LocalReaderProvisionAction.VERIFY),
        context=_context(registry, AccessAction.RESULT),
    )

    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert {item.destination_id for item in resolved.policy.disclosures} == {_DESTINATION}


@pytest.mark.parametrize(
    "subject_ref",
    [profile_operation_subject(str(PROFILE_ID)), str(PROFILE_ID), "9b0c2f4e-5a1d-4c3b-8e7f-0a1b2c3d4e5f"],
)
def test_a_subject_other_than_the_machines_reader_is_refused(subject_ref: str) -> None:
    registry = _registry()

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(LocalReaderProvisionAction.VERIFY, subject_ref=subject_ref),
            context=_context(registry),
        )

    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
