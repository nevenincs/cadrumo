"""The reader and browser provisioning operations resolve to one access whichever frontend submits them."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...core.config import Settings
from ...core.model_catalogue import ModelRole
from ...core.operations import profile_operation_subject
from ..browser_runtime_operation import (
    BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
    BROWSER_RUNTIME_OPERATION_SUBJECT,
    BrowserRuntimeProvisionRequest,
    build_browser_runtime_operation_definition,
    build_browser_runtime_operation_registration,
)
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


@dataclass(frozen=True, slots=True)
class _Case:
    """One request of the provisioning family and whether it can change what the machine holds."""

    definition_id: str
    subject_ref: str
    payload: BaseModel
    commits: bool


def _provision(action: LocalReaderProvisionAction, **values: object) -> _Case:
    return _Case(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest.model_validate({"action": action, **values}),
        commits=action is not LocalReaderProvisionAction.VERIFY,
    )


_CASES = {
    "install": _provision(LocalReaderProvisionAction.INSTALL, consent=True),
    "start": _provision(LocalReaderProvisionAction.START),
    "pull": _provision(LocalReaderProvisionAction.PULL),
    "pull-model": _provision(LocalReaderProvisionAction.PULL, model="qwen3:4b"),
    "load": _provision(LocalReaderProvisionAction.LOAD, role=ModelRole.TEXT_EXTRACTION),
    "verify": _provision(LocalReaderProvisionAction.VERIFY, role=ModelRole.TEXT_EXTRACTION),
    "verify-model": _provision(LocalReaderProvisionAction.VERIFY, model="qwen3:4b"),
    "remove": _provision(LocalReaderProvisionAction.REMOVE, role=ModelRole.TEXT_EXTRACTION),
    "setup": _provision(LocalReaderProvisionAction.SETUP, consent=True),
    "status": _Case(
        LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        LOCAL_READER_OPERATION_SUBJECT,
        LocalReaderStatusRequest(probe=False),
        commits=False,
    ),
    "probe": _Case(
        LOCAL_READER_STATUS_OPERATION_DEFINITION_ID,
        LOCAL_READER_OPERATION_SUBJECT,
        LocalReaderStatusRequest(probe=True),
        commits=False,
    ),
    "report": _Case(
        LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        LOCAL_READER_OPERATION_SUBJECT,
        LocalReaderReportRequest(),
        commits=False,
    ),
    "browser": _Case(
        BROWSER_RUNTIME_OPERATION_DEFINITION_ID,
        BROWSER_RUNTIME_OPERATION_SUBJECT,
        BrowserRuntimeProvisionRequest(),
        commits=True,
    ),
}


def _spawn(executable: Path, environment: object) -> int:
    raise AssertionError(f"access resolution started {executable} with {environment}")


def _install(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    raise AssertionError(f"access resolution ran {installer} for {executable} within {timeout_s}")


def _probe(model: str, settings: Settings) -> RoleFitnessOutcome:
    raise AssertionError(f"access resolution probed {model} under {settings}")


def _install_browser(timeout_s: float) -> int:
    raise AssertionError(f"access resolution downloaded a browser within {timeout_s}")


def _registry() -> OperationRegistry:
    provision = build_local_reader_operation_definition(spawn=_spawn, run_installer=_install, text_probe=_probe)
    status = build_local_reader_status_definition(text_probe=_probe)
    report = build_local_reader_report_definition()
    browser = build_browser_runtime_operation_definition(run_installer=_install_browser)
    return OperationRegistry(
        definitions=(browser, provision, report, status),
        public_registrations=(
            build_browser_runtime_operation_registration(browser),
            build_local_reader_operation_registration(provision),
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


def test_the_cases_cover_every_provisioning_action_and_every_operation_of_the_family() -> None:
    actions = {case.payload.action for case in _CASES.values() if isinstance(case.payload, LocalReaderProvisionRequest)}

    assert actions == set(LocalReaderProvisionAction)
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
    assert (AccessAction.COMMIT in on_cli.policy.actions) is case.commits
    for frontend in OperationFrontendProjection:
        on_frontend = resolve_operation_access(
            registry=registry, request=_request(case), context=replace(context, frontend=frontend)
        )
        assert on_frontend.policy == on_cli.policy, frontend
        assert on_frontend.request == on_cli.request.model_copy(update={"frontend": frontend}), frontend


@pytest.mark.parametrize("name", sorted(_CASES))
def test_a_scope_that_holds_no_commit_submits_the_reads_and_no_request_that_can_change_the_machine(
    name: str,
) -> None:
    case = _CASES[name]
    registry = _registry()
    resolved = resolve_operation_access(registry=registry, request=_request(case), context=_context(registry, case))

    decision = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)

    if case.commits:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.OPERATION_DENIED
    else:
        assert isinstance(decision, AccessAllowed)


@pytest.mark.parametrize("name", ["verify", "status", "report", "browser"])
def test_the_result_discloses_profile_values_to_the_requesting_destination_alone(name: str) -> None:
    case = _CASES[name]
    registry = _registry()
    resolved = resolve_operation_access(
        registry=registry, request=_request(case), context=_context(registry, case, AccessAction.RESULT)
    )

    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert {item.destination_id for item in resolved.policy.disclosures} == {_DESTINATION}


@pytest.mark.parametrize("name", ["verify", "status", "report", "browser"])
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


def test_the_readers_subject_does_not_open_the_browsers_operation_nor_the_reverse() -> None:
    registry = _registry()
    crossed = {"status": BROWSER_RUNTIME_OPERATION_SUBJECT, "browser": LOCAL_READER_OPERATION_SUBJECT}

    for name, subject_ref in crossed.items():
        case = _CASES[name]
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry, request=_request(case, subject_ref=subject_ref), context=_context(registry, case)
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
