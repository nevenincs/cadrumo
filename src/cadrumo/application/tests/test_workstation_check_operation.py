"""Complete workstation read snapshots, exact worker identity and disclosure policy."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ...core.capabilities import ServiceCapability
from ...core.config import override_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .. import workstation_check as service
from .. import workstation_check_operation as module
from ..auth.operator_probe_ports import (
    CertificateHealthProbeRequest,
    CertificateHealthProbeResult,
    ClaveIdentityProbeResult,
    OperatorProbePorts,
)
from ..ledger.tests.bulk_classify_operation_support import EffectEvents, PrivateOperands
from ..modelo.tests.m036_operation_support import PROFILE_ID, policy_decision
from ..operations.access_resolution import OperationAccessContext, resolve_operation_access
from ..operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicNamedScalar
from ..operations.registry import OperationFrontendProjection, OperationRegistry
from ..operator_actions.models import ConditionEvidence, PreconditionVerdict
from ..preflight import HealthSeverity, PreflightCheck
from ..provisioning import DependencyStatus
from ..user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenied,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.capabilities import CapabilityDecision, CapabilitySource
from ..workstation_check import WorkstationCheckReport
from ..workstation_check_operation import (
    WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
    WorkstationCheckExecutionResult,
    WorkstationCheckPorts,
    WorkstationCheckProjection,
    WorkstationCheckRequest,
    WorkstationDependencySnapshot,
    build_workstation_check_definition,
    build_workstation_check_registration,
    project_workstation_check_result,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class UnusedProbes:
    """The report fixture must not use external operator probe capabilities."""

    def is_bound(self) -> bool:
        """Reject an unintended native-session observation."""
        raise AssertionError("report fixture must not probe a native session")

    def evaluate(self, request: CertificateHealthProbeRequest) -> CertificateHealthProbeResult:
        """Reject an unintended certificate read."""
        raise AssertionError("report fixture must not read a certificate")

    def classify(self, raw: str) -> ClaveIdentityProbeResult:
        """Reject an unintended identity classification."""
        raise AssertionError("report fixture must not classify an identity")


class NoCommit:
    """A read-only operation has no authority to enter a mutation section."""

    def irreversible_section(self) -> AbstractAsyncContextManager[None]:
        raise AssertionError("workstation check must not enter COMMIT")


def _probes() -> OperatorProbePorts:
    unused = UnusedProbes()
    return OperatorProbePorts(active_profile_session=unused, certificate_health=unused, clave_identity=unused)


def _verdict() -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id="workstation.synthetic.available",
        evidence=(
            ConditionEvidence(
                condition_id="workstation.synthetic.available",
                evidence_id="workstation.synthetic.available.observed",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"available": False, "bytes_free": 0, "provider": "synthetic"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _report() -> WorkstationCheckReport:
    verdict = _verdict()
    return WorkstationCheckReport(
        profile_id=PROFILE_ID,
        capabilities=tuple(
            CapabilityDecision(
                capability=capability,
                enabled=capability is ServiceCapability.LLM_VISION,
                source=CapabilitySource.PROFILE
                if capability is ServiceCapability.LLM_VISION
                else CapabilitySource.DEFAULT,
                reason="synthetic explicit posture"
                if capability is ServiceCapability.LLM_VISION
                else "synthetic default",
            )
            for capability in ServiceCapability
        ),
        dependencies=(
            DependencyStatus(
                service="synthetic:vision",
                available=False,
                facts={"installed": False, "count": 0, "model": "synthetic"},
                precondition_verdict=verdict,
            ),
            DependencyStatus(service="synthetic:optional", available=True, facts={"installed": True, "count": 1}),
        ),
        preflight=(
            PreflightCheck(
                check="synthetic:storage",
                healthy=False,
                severity=HealthSeverity.ERROR,
                facts={"writable": False, "free_bytes": 0},
                precondition_verdict=verdict,
            ),
            PreflightCheck(
                check="synthetic:registry",
                healthy=True,
                severity=HealthSeverity.OK,
                facts={"records": 4, "assembled": True},
            ),
        ),
        issues=("synthetic:vision",),
    )


def _context(
    operation: PinnedAuthorityOperation, events: EffectEvents, operands: PrivateOperands
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(PROFILE_ID)),
                ),
                authority_operation=operation,
                cancellation=NoCommit(),
                events=events,
                operands=operands,
            ),
        ),
    )


def _request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=WorkstationCheckRequest(profile_id=PROFILE_ID),
    )


def test_real_registration_compiles_closed_cli_only_read_contract() -> None:
    """The production compiler accepts every nested scalar/verdict projection."""

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        raise AssertionError("schema compilation must not compose a private report")

    definition = build_workstation_check_definition(factory)
    registration = build_workstation_check_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    assert registry.lookup_public_registration(definition.definition_id).contract.result_schema is not None
    assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


def test_whole_report_roundtrip_preserves_source_reason_scalar_types_and_verdicts() -> None:
    """Conversion retains every canonical row while the existing CLI chooses its fields."""
    report = _report()
    projection = WorkstationCheckProjection.from_report(report)
    restored = WorkstationCheckProjection.model_validate_json(projection.model_dump_json()).to_report()
    assert restored == report
    facts = restored.dependencies[0].facts
    assert type(facts["installed"]) is bool and type(facts["count"]) is int and facts["count"] == 0
    assert restored.preflight[0].precondition_verdict == report.preflight[0].precondition_verdict
    assert restored.capabilities[0].reason == report.capabilities[0].reason


def test_dependency_snapshot_refuses_duplicate_facts_instead_of_dropping_values() -> None:
    """A closed scalar collection still must preserve canonical map uniqueness."""
    with pytest.raises(ValidationError, match="duplicate"):
        WorkstationDependencySnapshot(
            service="synthetic",
            available=True,
            facts=(PublicNamedScalar(key="count", value=0), PublicNamedScalar(key="count", value=1)),
        )


def test_exact_worker_executes_one_report_without_commit(authority_operation: PinnedAuthorityOperation) -> None:
    """Factory and report keep the exact pin and produce only credential-free journal facts."""
    events, operands = EffectEvents(), PrivateOperands()
    calls: list[str] = []
    probes = _probes()

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        assert profile_id == PROFILE_ID and operation is authority_operation
        calls.append("compose")

        def report() -> WorkstationCheckReport:
            calls.append("report")
            return _report()

        return WorkstationCheckPorts(PROFILE_ID, operation, probes, report)

    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        result_ref = asyncio.run(
            build_workstation_check_definition(factory)
            .executor_factory.create()
            .execute(_request(), _context(authority_operation, events, operands))
        )
    assert result_ref == "d" * 64 and calls == ["compose", "report"]
    assert events.effects == [OperationEffect.NONE] and events.phases == [WORKSTATION_CHECK_OPERATION_DEFINITION_ID]
    assert isinstance(operands.values[0], WorkstationCheckExecutionResult)
    assert operands.values[0].projection.to_report() == _report()


@pytest.mark.parametrize("foreign", ["worker", "ports", "report"])
def test_profile_mismatch_refuses_before_disclosing_report(
    authority_operation: PinnedAuthorityOperation, foreign: str
) -> None:
    """Each owning boundary correlates its independent immutable profile identity."""
    events, operands = EffectEvents(), PrivateOperands()
    calls: list[str] = []
    other = uuid4()

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        calls.append("compose")
        return WorkstationCheckPorts(
            other if foreign == "ports" else PROFILE_ID,
            operation,
            _probes(),
            lambda: replace(_report(), profile_id=other if foreign == "report" else PROFILE_ID),
        )

    with (
        override_settings(cadrumo_active_profile=str(other if foreign == "worker" else PROFILE_ID)),
        pytest.raises(ProfileAccessRefusedError),
    ):
        asyncio.run(
            build_workstation_check_definition(factory)
            .executor_factory.create()
            .execute(_request(), _context(authority_operation, events, operands))
        )
    assert not operands.values
    assert calls == ([] if foreign == "worker" else ["compose"])


def test_report_size_refusal_does_not_truncate_or_disclose(
    authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The complete report is refused at its byte budget rather than silently shortened."""
    report = _report()
    assert module.PROJECTION_DOCUMENT_MAX_BYTES == 16_777_216
    monkeypatch.setattr(module, "PROJECTION_DOCUMENT_MAX_BYTES", 256)
    events, operands = EffectEvents(), PrivateOperands()

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        return WorkstationCheckPorts(PROFILE_ID, operation, _probes(), lambda: report)

    with override_settings(cadrumo_active_profile=str(PROFILE_ID)), pytest.raises(ProfileAccessRefusedError):
        asyncio.run(
            build_workstation_check_definition(factory)
            .executor_factory.create()
            .execute(_request(), _context(authority_operation, events, operands))
        )
    assert not operands.values and events.effects == [OperationEffect.NONE]
    assert WorkstationCheckProjection.from_report(report).to_report() == report


def test_canonical_report_keeps_issue_exit_semantics_and_checks_profile_each_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report-only preflight errors do not become capability/dependency exit issues."""
    report = _report()
    observed: list[str] = []
    decisions = {row.capability: row for row in report.capabilities}

    def capability(capability: ServiceCapability) -> CapabilityDecision:
        observed.append(capability.value)
        return decisions[capability]

    def dependencies() -> tuple[tuple[DependencyStatus, ...], DependencyStatus, tuple[DependencyStatus, ...]]:
        observed.append("dependencies")
        return report.dependencies, report.dependencies[0], ()

    def preflight(**kwargs: object) -> tuple[PreflightCheck, ...]:
        assert kwargs["operator_probe_ports"] is probes
        observed.append("preflight")
        return report.preflight

    probes = _probes()
    monkeypatch.setattr(service, "resolve_active_capability", capability)
    monkeypatch.setattr(service, "_probe_dependency_statuses", dependencies)
    monkeypatch.setattr(service, "run_preflight_checks", preflight)
    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        actual = service.run_workstation_check(
            profile_id=PROFILE_ID, operator_probe_ports=probes, object_path_suffix_length=1
        )
    assert actual == report
    assert observed == [*(cap.value for cap in ServiceCapability), "dependencies", "preflight"]


def test_canonical_report_profile_change_blocks_next_private_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """One capability read cannot lend its profile identity to the next read."""
    active = str(PROFILE_ID)
    calls: list[ServiceCapability] = []

    def capability(capability: ServiceCapability) -> CapabilityDecision:
        nonlocal active
        calls.append(capability)
        active = str(uuid4())
        return CapabilityDecision(
            capability=capability, enabled=False, source=CapabilitySource.DEFAULT, reason="synthetic"
        )

    monkeypatch.setattr(service, "require_active_bucket_id", lambda: active)
    monkeypatch.setattr(service, "resolve_active_capability", capability)
    with pytest.raises(ProfileAccessRefusedError):
        service.run_workstation_check(
            profile_id=PROFILE_ID, operator_probe_ports=_probes(), object_path_suffix_length=1
        )
    assert calls == [next(iter(ServiceCapability))]


def test_real_policy_is_period_independent_exact_destination_profile_values(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Configuration output needs its reviewed destination; observation contains only metadata."""

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        raise AssertionError("policy evaluation must not execute report probes")

    definition = build_workstation_check_definition(factory)
    registration = build_workstation_check_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    resolved = resolve_operation_access(registry=registry, request=_request(), context=context)
    assert (
        resolved.request.period_independent
        and not resolved.request.periods
        and not resolved.policy.requires_all_periods
    )
    assert {row.category for row in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert isinstance(policy_decision(resolved, registry, disclosures=resolved.policy.disclosures), AccessAllowed)
    assert isinstance(policy_decision(resolved, registry, disclosures=frozenset[DisclosurePermission]()), AccessDenied)
    assert isinstance(
        policy_decision(
            resolved,
            registry,
            disclosures=frozenset(
                row.model_copy(update={"destination_id": uuid4()}) for row in resolved.policy.disclosures
            ),
        ),
        AccessDenied,
    )
    observed = resolve_operation_access(
        registry=registry, request=_request(), context=replace(context, action=AccessAction.OBSERVE)
    )
    assert {row.category for row in observed.policy.disclosures} == {DisclosureCategory.OPERATION_METADATA}
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry, request=_request(), context=replace(context, frontend=OperationFrontendProjection.MCP)
        )


def test_receipt_projector_refuses_mutation_or_foreign_identity() -> None:
    """A complete snapshot cannot override the canonical read-only terminal receipt."""
    result = WorkstationCheckExecutionResult(projection=WorkstationCheckProjection.from_report(_report()))
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=now(),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )
    assert project_workstation_check_result(result, receipt) == result.projection
    with pytest.raises(ValueError, match="contradicts"):
        project_workstation_check_result(result, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))
