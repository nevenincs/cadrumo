"""Registered-executor conformance scenario for the exact-profile workstation check."""

from __future__ import annotations

from ...application.local_reader import LOCAL_AI_PROGRAM_SERVICE
from ...application.operations.public_scalar import PublicNamedScalar, PublicScalar
from ...application.provisioning_browser import PLAYWRIGHT_BROWSER_SERVICE
from ...application.workstation_check_operation import (
    WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
    WorkstationCheckProjection,
    WorkstationCheckRequest,
)
from ...core.auth_provider import AuthProviderKind
from ...core.capabilities import ServiceCapability
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.optional_extras import OPTIONAL_EXTRAS
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_GOOGLE_EXTRA = "extra:google"
_CLOUD_PERMISSION_ISSUE = "cloud_evidence_upload:deployment_permission"


def _fact(row_facts: tuple[PublicNamedScalar, ...], key: str) -> PublicScalar:
    matches = [item.value for item in row_facts if item.key == key]
    assert len(matches) == 1, key
    return matches[0]


def _prepare_check(context: ConformanceFamilyContext) -> ConformancePreparation:
    gestor_mode = load_settings().cadrumo_evidence_gestor_mode
    cloud_upload_permitted = load_settings().cadrumo_evidence_cloud_upload_permitted
    request = WorkstationCheckRequest(profile_id=context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(WorkstationCheckProjection)
        assert projection.profile_id == context.profile_id
        assert [row.capability for row in projection.capabilities] == list(ServiceCapability)
        for row in projection.capabilities:
            barred = row.capability is ServiceCapability.CLOUD_EVIDENCE_UPLOAD and gestor_mode
            assert row.enabled is (False if barred else row.capability.default_enabled), row.capability
            assert row.source.value == ("safety_floor" if barred else "default"), row.capability
            assert row.capability.value in row.reason
        assert [row.service for row in projection.dependencies] == [
            LOCAL_AI_PROGRAM_SERVICE,
            "model-runtime-hardware-floor",
            "local-inference-hardware",
            PLAYWRIGHT_BROWSER_SERVICE,
            *(f"extra:{extra.extra}" for extra in OPTIONAL_EXTRAS),
        ]
        by_service = {row.service: row for row in projection.dependencies}
        program = by_service[LOCAL_AI_PROGRAM_SERVICE]
        assert program.available is False
        assert not {"role", "model"} & {item.key for item in program.facts}, "the program row judges no model"
        assert _fact(program.facts, "local_ai_state") in {"absent", "blocked", "unknown"}
        assert program.precondition_verdict is not None
        checks = [row.check for row in projection.preflight]
        provider_checks = [f"auth-provider:{kind.value}" for kind in AuthProviderKind]
        assert checks[: len(provider_checks)] == provider_checks
        assert checks[-1] == "portal-registry:health"
        assert len(set(checks)) == len(checks)
        assert {"storage:local-root", "env:configuration"} <= set(checks)
        storage_root = next(row for row in projection.preflight if row.check == "storage:local-root")
        assert storage_root.healthy is True
        enabled = {row.capability: row.enabled for row in projection.capabilities}
        expected_issues: list[str] = []
        if enabled[ServiceCapability.GOOGLE_EXPORT] and (not by_service[_GOOGLE_EXTRA].available):
            expected_issues.append(_GOOGLE_EXTRA)
        if enabled[ServiceCapability.CLOUD_EVIDENCE_UPLOAD] and (not cloud_upload_permitted):
            expected_issues.append(_CLOUD_PERMISSION_ISSUE)
        assert list(projection.issues) == expected_issues
        restored = projection.to_report()
        assert WorkstationCheckProjection.from_report(restored) == projection

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)), request=request, verify=verify
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == WORKSTATION_CHECK_OPERATION_DEFINITION_ID:
        return _prepare_check(context)
    raise AssertionError(f"no workstation conformance scenario for {context.definition.definition_id}")


WORKSTATION_CHECK_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (WORKSTATION_CHECK_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _retained_workstation_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id == "diagnostics.workstation.check":

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(WorkstationCheckProjection)
            assert result.profile_id == context.profile_id
            assert {row.capability for row in result.capabilities} == set(ServiceCapability)
            services = {row.service for row in result.dependencies}
            assert "extra:google" in services and result.preflight
            assert len(services) == len(result.dependencies)
            assert not any(row.service.startswith("local-reader:") for row in result.dependencies)
            (program,) = (row for row in result.dependencies if row.service == LOCAL_AI_PROGRAM_SERVICE)
            assert not program.available

        return ConformancePreparation(
            profile_operation_subject(str(context.profile_id)),
            WorkstationCheckRequest(profile_id=context.profile_id),
            verify=verify,
        )
    raise AssertionError(context.definition.definition_id)


WORKSTATION_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            "diagnostics.workstation.check",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("diagnostics.workstation.check",),
        ),
    ),
    prepare=_retained_workstation_prepare,
)
