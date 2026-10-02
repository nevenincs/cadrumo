"""Quickfile public authority, closed stage outputs and concrete effect settlement.

These isolated policy/fence cases do not claim native filing or runtime acceptance.
The existing CLI chain tests own canonical tax and export behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.errors.error_codes import get_registered_error_code
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...ledger.commit_fence import run_with_ledger_commit_fence
from ...ledger.persistence_ports import LedgerPersistenceConflictError
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import quickfile_operation as module
from ..action_errors import WorkUnitNotFoundError
from ..quickfile import (
    QUICKFILE_STAGE_ORDER,
    QuickfileResult,
    QuickfileStage,
    QuickfileStageOutcome,
    QuickfileStageStatus,
)
from ..quickfile_operation_contracts import QuickfileProjection, QuickfileRequest, QuickfileStageFacts
from ..quickfile_operation_ports import QuickfileOperationPorts
from .m036_operation_support import INSTANT, PROFILE_ID, Subject, policy_decision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _unreachable_factory(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    mutation_writer: Callable[[Callable[[], None]], None],
) -> QuickfileOperationPorts:
    raise AssertionError("this boundary must refuse before resolving private capabilities")


def _request(tmp_path: Path, *, profile_id: UUID = PROFILE_ID, bucket_id: UUID | None = None) -> QuickfileRequest:
    return QuickfileRequest(
        profile_id=profile_id,
        bucket_id=bucket_id,
        modelo="130",
        period=PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
        output_path=str(tmp_path / "filing.txt"),
        actor="synthetic-human",
    )


def _registry() -> OperationRegistry:
    definition = module.build_quickfile_definition(_unreachable_factory)
    return OperationRegistry(
        definitions=(definition,), public_registrations=(module.build_quickfile_registration(definition),)
    )


def _halted() -> QuickfileProjection:
    error = WorkUnitNotFoundError("private exception text", context={"arbitrary": "private source evidence"})
    result = QuickfileResult(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        registry_revision_id="",
        stages=(
            QuickfileStageOutcome(
                stage=QuickfileStage.READINESS,
                status=QuickfileStageStatus.REFUSED,
                message=str(error),
                context={"source": "private source evidence"},
                refusal=error,
            ),
            *(
                QuickfileStageOutcome(stage=stage, status=QuickfileStageStatus.SKIPPED)
                for stage in QUICKFILE_STAGE_ORDER[1:]
            ),
        ),
        completed=False,
        stopped_at_stage=QuickfileStage.READINESS,
        readiness=None,
        work_unit=None,
        calculation_revision=None,
        verification_report=None,
        export_result=None,
    )
    return QuickfileProjection.from_result(result, profile_id=PROFILE_ID, write_count=0, effect=OperationEffect.NONE)


def test_real_registry_compiles_complete_secure_human_schema() -> None:
    registry = _registry()
    definition = registry.lookup(module.QUICKFILE_OPERATION_DEFINITION_ID)
    contract = registry.lookup_public_contract(definition.definition_id)
    assert contract.request_schema.schema_id == "modelo.quickfile.request"
    assert contract.result_schema is not None and contract.result_schema.schema_id == "modelo.quickfile.result"
    assert definition.result_type is module.QuickfileExecutionResult
    assert definition.result_type is not QuickfileProjection
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert definition.capabilities.permitted_effects == frozenset(OperationEffect)
    assert "ordinary_m303_filing_evidence" in QuickfileRequest.model_fields
    assert "detail_rows" in QuickfileRequest.model_fields


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_result_actual_policy_requires_human_exact_destination_and_both_categories(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
    missing: DisclosureCategory | None,
) -> None:
    registry = _registry()
    definition = registry.lookup(module.QUICKFILE_OPERATION_DEFINITION_ID)
    registration = module.build_quickfile_registration(definition)
    assert registration.access_resolver is not None
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=_request(tmp_path),
    )
    resolved = registration.access_resolver(
        request,
        OperationAccessContext(
            profile_id=PROFILE_ID,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=registry.lookup_public_contract(definition.definition_id),
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )
    disclosures = frozenset(row for row in resolved.policy.disclosures if row.category is not missing)
    decision = policy_decision(resolved, registry, disclosures=disclosures, human=True)
    assert isinstance(decision, AccessAllowed if missing is None else AccessDenied)
    assert resolved.request.destination_id == next(iter(resolved.policy.disclosures)).destination_id
    assert resolved.policy.definition_contract_digest == registration.contract.definition_contract_digest
    assert resolved.request.periods == frozenset({_request(tmp_path).period.to_period()})
    if missing is None:
        assert isinstance(policy_decision(resolved, registry, disclosures=disclosures), AccessDenied)
        wrong_destination = frozenset(row.model_copy(update={"destination_id": uuid4()}) for row in disclosures)
        assert isinstance(policy_decision(resolved, registry, disclosures=wrong_destination, human=True), AccessDenied)


def test_agent_frontend_has_typed_unavailable_purpose(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
) -> None:
    registry = _registry()
    registration = registry.lookup_public_registration(module.QUICKFILE_OPERATION_DEFINITION_ID)
    assert registration.access_resolver is not None
    request = OperationRequest[BaseModel](
        definition_id=module.QUICKFILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=_request(tmp_path),
    )
    with pytest.raises(ProfileAccessRefusedError):
        registration.access_resolver(
            request,
            OperationAccessContext(
                profile_id=PROFILE_ID,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.MCP,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
                authority_operation=authority_operation,
            ),
        )


@pytest.mark.parametrize("action", [AccessAction.START, AccessAction.RESUME, AccessAction.COMMIT])
def test_worker_lifecycle_policy_requires_exact_admitted_period_and_current_scope(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
    action: AccessAction,
) -> None:
    registry = _registry()
    definition = registry.lookup(module.QUICKFILE_OPERATION_DEFINITION_ID)
    registration = registry.lookup_public_registration(definition.definition_id)
    assert registration.access_resolver is not None
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=_request(tmp_path),
    )
    destination_id = uuid4()
    submitted = registration.access_resolver(
        request,
        OperationAccessContext(
            profile_id=PROFILE_ID,
            destination_id=destination_id,
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=authority_operation,
        ),
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=destination_id,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=submitted.request,
        authority_operation=authority_operation,
    )
    resolved = registration.access_resolver(request, context)
    assert resolved.request.action is action
    assert resolved.request.periods == submitted.request.periods
    assert not resolved.policy.transaction_authority_required
    assert isinstance(
        policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True), AccessAllowed
    )
    assert isinstance(
        policy_decision(
            resolved, registry, disclosures=resolved.policy.disclosures, human=True, operations=frozenset()
        ),
        AccessDenied,
    )
    changed_period = _request(tmp_path).model_copy(
        update={"period": PublicPeriod.from_period(Period.from_year_and_code(2026, "2T"))}
    )
    with pytest.raises(ProfileAccessRefusedError):
        registration.access_resolver(request.model_copy(update={"payload": changed_period}), context)


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_profile", [False, True])
async def test_profile_and_explicit_bucket_refuse_before_factory(
    authority_operation: PinnedAuthorityOperation,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    foreign_profile: bool,
) -> None:
    subject = Subject(authority_operation)
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(PROFILE_ID))
    payload = _request(
        tmp_path, profile_id=uuid4() if foreign_profile else PROFILE_ID, bucket_id=None if foreign_profile else uuid4()
    )
    request = OperationRequest[QuickfileRequest](
        definition_id=module.QUICKFILE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(payload.profile_id)),
        payload=payload,
    )
    with pytest.raises(ProfileAccessRefusedError):
        await module.QuickfileExecutor(_unreachable_factory).execute(
            request, subject.context(module.QUICKFILE_OPERATION_DEFINITION_ID)
        )
    assert subject.fence.entries == 0 and not subject.operands.values


def test_stage_projection_retains_order_and_registered_error_without_generic_exception_data() -> None:
    projection = _halted()
    stage = projection.stages[0]
    expected = get_registered_error_code(WorkUnitNotFoundError())
    assert stage.error is not None and (stage.error.code, stage.error.message_key) == (
        expected.code,
        expected.message_key,
    )
    assert tuple(row.stage for row in projection.stages) == QUICKFILE_STAGE_ORDER
    assert all(row.status is QuickfileStageStatus.SKIPPED for row in projection.stages[1:])
    assert "private exception text" not in projection.model_dump_json()
    assert "private source evidence" not in projection.model_dump_json()
    assert QuickfileStageFacts(ready=False, missing_bindings=0).to_context() == {
        "ready": "false",
        "missing_bindings": "0",
    }


def test_projector_requires_exact_whole_chain_receipt() -> None:
    projection = _halted()
    retained = module.QuickfileExecutionResult(projection=projection)
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=module.QUICKFILE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=INSTANT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )
    assert module.project_quickfile_result(retained, receipt) is projection
    with pytest.raises(ValueError):
        module.project_quickfile_result(retained, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))
    with pytest.raises(ValueError):
        module.project_quickfile_result(projection, receipt)
    with pytest.raises(ValidationError):
        QuickfileProjection.model_validate(projection.model_dump(mode="python") | {"write_count": 1})
    with pytest.raises(ValidationError):
        QuickfileProjection.model_validate(projection.model_dump(mode="python") | {"stages": projection.stages[:-1]})


@pytest.mark.asyncio
@pytest.mark.parametrize("late_failure", ["conflict", "uncertain", "none"])
async def test_prior_confirmed_write_survives_late_failure_and_noop(
    authority_operation: PinnedAuthorityOperation,
    late_failure: str,
) -> None:
    subject = Subject(authority_operation)
    tracker = module._Writes()
    writes: list[str] = []

    def write() -> None:
        assert subject.fence.active
        writes.append("confirmed")

    def fail() -> None:
        assert subject.fence.active
        if late_failure == "conflict":
            raise LedgerPersistenceConflictError("known prewrite rejection")
        writes.append("committed-before-error")
        raise ValueError("uncertain writer outcome")

    def work() -> None:
        assert not subject.fence.active
        tracker.call_writer(write)
        assert not subject.fence.active
        if late_failure != "none":
            tracker.call_writer(fail)

    context = subject.context(module.QUICKFILE_OPERATION_DEFINITION_ID)
    if late_failure == "none":
        await run_with_ledger_commit_fence(work, tracker=tracker, context=context, task_name="quickfile-test")
        assert tracker.effect(incomplete=False) is OperationEffect.UPDATED
    else:
        with pytest.raises(LedgerPersistenceConflictError if late_failure == "conflict" else ValueError):
            await run_with_ledger_commit_fence(work, tracker=tracker, context=context, task_name="quickfile-test")
        assert tracker.effect(incomplete=True) is (
            OperationEffect.PARTIAL if late_failure == "conflict" else OperationEffect.UNKNOWN
        )
    assert tracker.count == 1 and writes[0] == "confirmed"


def test_input_grammar_preserves_local_elections_and_rejects_relative_output(tmp_path: Path) -> None:
    request = _request(tmp_path)
    assert request.inputs.to_calculation_fields().binding_overrides == ()
    assert request.refund_election is not None
    assert request.payment_election is not None
    assert request.prior_domiciliation_election is not None
    with pytest.raises(ValidationError):
        QuickfileRequest.model_validate(request.model_dump(mode="python") | {"output_path": "relative.txt"})
    registry = _registry()
    definition = registry.lookup(module.QUICKFILE_OPERATION_DEFINITION_ID)
    with pytest.raises(ValueError):
        module.build_quickfile_registration(definition.model_copy(update={"result_type": BaseModel}))
