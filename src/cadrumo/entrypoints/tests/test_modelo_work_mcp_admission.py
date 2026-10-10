"""Declaration preparation is open to an MCP session, and what stays the person's is not.

The production registry, its real access resolvers and the real executors run
over a stored profile. An agent may create, recalculate, verify and rename a
declaration. It may not supply a calculation's inputs or the Modelo 303 filing
facts, and what it records carries its own session label.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.calculation_request_fields import (
    ModeloCalculationInputFieldsV1,
    ModeloCalculationOverride,
)
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_change_contracts import ModeloWorkRenameRequest
from cadrumo.application.modelo.work_create_operation import ModeloWorkCreateRequest
from cadrumo.application.modelo.work_verification_contracts import (
    ModeloWorkVerifyPublicResultV2,
    ModeloWorkVerifyRequest,
)
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.mcp_admission import McpRuling, mcp_admission_decision
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    SessionKind,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.tests.modelo_operation_test_support import seeded_modelo_calculation_revision

from .test_operation_catalogue import _registry
from .test_registered_executor_conformance import _CloseWitness, _runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP
_OPENED = ("modelo.work.calculate", "modelo.work.create", "modelo.work.rename", "modelo.work.verify")
_SUPPLIED_ACTOR = "typed by the caller"
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_M303_FILING_FACTS = ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(joint_return_elected=False)


def _context(
    registry: OperationRegistry,
    request: OperationRequest[BaseModel],
    *,
    profile_id: UUID,
    frontend: OperationFrontendProjection,
    operation: PinnedAuthorityOperation,
    action: AccessAction = AccessAction.SUBMIT,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=operation,
    )


def _seeded_unit(profile_id: UUID, *, operation: PinnedAuthorityOperation) -> tuple[WorkUnit, str]:
    """One stored work unit and the id of its real calculation head."""
    revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
    revision = CalculationRevisionCatalogueRepository().load().get(revision_id)
    assert revision is not None
    unit = WorkUnitCatalogueRepository().load().get(revision.work_unit_id)
    assert unit is not None
    return unit, revision_id


def _calculation(unit: WorkUnit, payload: ModeloWorkCalculateRequest) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id="modelo.work.calculate", subject_ref=unit.work_unit_id, payload=payload
    )


def _ordinary_requests(unit: WorkUnit, revision_id: str, profile_id: UUID) -> tuple[OperationRequest[BaseModel], ...]:
    """One request of each opened operation that carries nothing reserved for the person."""
    return (
        _calculation(unit, ModeloWorkCalculateRequest(work_unit_id=unit.work_unit_id, actor=_SUPPLIED_ACTOR)),
        OperationRequest[BaseModel](
            definition_id="modelo.work.verify",
            subject_ref=unit.work_unit_id,
            payload=ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=_SUPPLIED_ACTOR),
        ),
        OperationRequest[BaseModel](
            definition_id="modelo.work.rename",
            subject_ref=unit.work_unit_id,
            payload=ModeloWorkRenameRequest(
                work_unit_id=unit.work_unit_id,
                new_name="Renamed by the test",
                observed_name=unit.name,
                observed_updated_at=unit.updated_at,
                actor=_SUPPLIED_ACTOR,
            ),
        ),
        OperationRequest[BaseModel](
            definition_id="modelo.work.create",
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=ModeloWorkCreateRequest(
                profile_id=profile_id,
                modelo=str(unit.modelo),
                period=PublicPeriod.from_period(unit.period),
                actor=_SUPPLIED_ACTOR,
                allow_not_applicable=True,
            ),
        ),
    )


def test_the_four_opened_operations_list_mcp_and_the_amendment_does_not() -> None:
    """An amendment records a local filing in one act, so it is not opened with the preparation steps."""
    registry = _registry()

    for definition_id in _OPENED:
        decision = mcp_admission_decision(definition_id)
        assert decision.ruling is McpRuling.ADMITTED, definition_id
        assert not decision.prerequisites, definition_id
        assert _MCP in registry.lookup(definition_id).permitted_frontends, definition_id
        assert _MCP in registry.lookup_public_contract(definition_id).permitted_frontends, definition_id
    assert mcp_admission_decision("modelo.work.calculate").sensitive_actions == (
        "explicit",
        "ordinary_m303_filing_evidence",
    )
    assert not mcp_admission_decision("modelo.work.verify").reaches_network
    assert mcp_admission_decision("modelo.work.amend").prerequisites
    assert _MCP not in registry.lookup("modelo.work.amend").permitted_frontends


def test_the_real_resolvers_admit_an_agent_for_ordinary_preparation_as_they_admit_a_person(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Each opened operation resolves for MCP exactly as for the command line and the terminal interface."""
    with _runtime(tmp_path / "admission", cleanup=_CloseWitness()) as (_driver, registry, profile_id):
        unit, revision_id = _seeded_unit(profile_id, operation=operation)

        for request in _ordinary_requests(unit, revision_id, profile_id):
            for frontend in (_CLI, _TUI, _MCP):
                access = resolve_operation_access(
                    registry=registry,
                    request=request,
                    context=_context(registry, request, profile_id=profile_id, frontend=frontend, operation=operation),
                )
                assert access.request.frontend is frontend, (request.definition_id, frontend)
                assert access.request.periods == frozenset({unit.period}), (request.definition_id, frontend)
                assert AccessAction.COMMIT in access.policy.actions, (request.definition_id, frontend)
                assert not access.policy.requires_human, (request.definition_id, frontend)


def _calculations_reserved_for_the_person(unit: WorkUnit) -> dict[str, OperationRequest[BaseModel]]:
    """One calculation per variant the recorded decision names as sensitive."""
    return {
        "explicit": _calculation(
            unit,
            ModeloWorkCalculateRequest(
                work_unit_id=unit.work_unit_id,
                actor=_SUPPLIED_ACTOR,
                caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
                inputs=ModeloCalculationInputFieldsV1(
                    casilla_overrides=(ModeloCalculationOverride(key="01", value="100.00"),)
                ),
            ),
        ),
        "ordinary_m303_filing_evidence": _calculation(
            unit,
            ModeloWorkCalculateRequest(
                work_unit_id=unit.work_unit_id,
                actor=_SUPPLIED_ACTOR,
                ordinary_m303_filing_evidence=_M303_FILING_FACTS,
            ),
        ),
    }


def test_a_calculation_that_states_what_is_the_persons_is_refused_to_an_agent_and_admitted_for_a_person(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Inputs of its own and the Modelo 303 filing facts are refused on MCP alone, at every access."""
    with _runtime(tmp_path / "reserved", cleanup=_CloseWitness()) as (_driver, registry, profile_id):
        unit, _revision_id = _seeded_unit(profile_id, operation=operation)
        reserved = _calculations_reserved_for_the_person(unit)

        assert tuple(reserved) == mcp_admission_decision("modelo.work.calculate").sensitive_actions
        for variant, stated in reserved.items():
            for action in (AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT):
                with pytest.raises(ProfileAccessRefusedError) as refused:
                    resolve_operation_access(
                        registry=registry,
                        request=stated,
                        context=_context(
                            registry, stated, profile_id=profile_id, frontend=_MCP, operation=operation, action=action
                        ),
                    )
                assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED, (variant, action)
            for frontend in (_CLI, _TUI):
                access = resolve_operation_access(
                    registry=registry,
                    request=stated,
                    context=_context(registry, stated, profile_id=profile_id, frontend=frontend, operation=operation),
                )
                assert access.request.frontend is frontend, variant
                assert access.request.periods == frozenset({unit.period}), variant


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an invocation it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == "modelo.work.verify"
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.HUMAN, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.parametrize(
    ("frontend", "recorded_actor"),
    [
        (_MCP, f"agent:mcp.human.{_SESSION_CLIENT}"),
        (_CLI, _SUPPLIED_ACTOR),
        (_TUI, _SUPPLIED_ACTOR),
    ],
    ids=["mcp", "cli", "tui"],
)
def test_verification_stores_the_session_label_for_an_agent_and_the_supplied_label_for_a_person(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded_actor: str,
) -> None:
    """The real executor never stores what an MCP caller typed as the actor of its report."""
    with _runtime(tmp_path / "actor", cleanup=_CloseWitness(), execution_caller_reader=_session_host(frontend)) as (
        driver,
        registry,
        profile_id,
    ):
        unit, revision_id = _seeded_unit(profile_id, operation=operation)
        payload = ModeloWorkVerifyRequest(calculation_revision_id=revision_id, actor=_SUPPLIED_ACTOR)

        submitted, observed = asyncio.run(
            driver.run(definition_id="modelo.work.verify", subject_ref=unit.work_unit_id, payload=payload)
        )

        terminal = observed.projection
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        contract = registry.lookup_public_contract("modelo.work.verify")
        assert contract.result_schema is not None
        resolved = asyncio.run(
            driver.services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ModeloWorkVerifyPublicResultV2,
            )
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        report = VerificationReportCatalogueRepository().load().get(resolved.projection.verification_report_id)
        assert report is not None
        assert report.verified_by == recorded_actor
