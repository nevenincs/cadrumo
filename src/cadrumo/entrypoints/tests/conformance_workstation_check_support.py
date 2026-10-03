"""Registered-executor conformance scenario for the exact-profile workstation check."""

from __future__ import annotations

from ...application.local_reader import EXTRACTION_READER_ROLES, local_reader_service
from ...application.operations.public_scalar import PublicNamedScalar, PublicScalar
from ...application.provisioning import LOCAL_MODEL_PROVISIONING_SERVICE
from ...application.provisioning_browser import PLAYWRIGHT_BROWSER_SERVICE
from ...application.workstation_check_operation import (
    WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
    WorkstationCheckProjection,
    WorkstationCheckRequest,
)
from ...application.workstation_contention import CONTENTION_ROW_ID
from ...core.auth_provider import AuthProviderKind
from ...core.capabilities import ServiceCapability
from ...core.config import load_settings
from ...core.model_catalogue import ModelRole
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
    # The family closes the local model runtime, so every reader probe reports an
    # unreachable runtime at the URL this very setting names.
    runtime_url = load_settings().cadrumo_llm_ollama_chat_url
    gestor_mode = load_settings().cadrumo_evidence_gestor_mode
    cloud_upload_permitted = load_settings().cadrumo_evidence_cloud_upload_permitted
    request = WorkstationCheckRequest(profile_id=context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(WorkstationCheckProjection)
        assert projection.profile_id == context.profile_id

        # One decision per capability, in declaration order. The enrolled profile
        # states no capability fact, so each resolves from its conservative default
        # unless the gestor bar takes the cloud upload capability outright.
        assert [row.capability for row in projection.capabilities] == list(ServiceCapability)
        for row in projection.capabilities:
            barred = row.capability is ServiceCapability.CLOUD_EVIDENCE_UPLOAD and gestor_mode
            assert row.enabled is (False if barred else row.capability.default_enabled), row.capability
            assert row.source.value == ("safety_floor" if barred else "default"), row.capability
            assert row.capability.value in row.reason

        # The dependency rows are the reader probes, the fixed hardware, contention,
        # provisioning and browser rows, then one row per declared optional extra.
        reader_services = [local_reader_service(role) for role in EXTRACTION_READER_ROLES]
        assert [row.service for row in projection.dependencies] == [
            *reader_services,
            "model-runtime-hardware-floor",
            "local-inference-hardware",
            CONTENTION_ROW_ID,
            LOCAL_MODEL_PROVISIONING_SERVICE,
            PLAYWRIGHT_BROWSER_SERVICE,
            *(f"extra:{extra.extra}" for extra in OPTIONAL_EXTRAS),
        ]
        by_service = {row.service: row for row in projection.dependencies}
        for role, service in zip(EXTRACTION_READER_ROLES, reader_services, strict=True):
            reader = by_service[service]
            assert reader.available is False, service
            assert _fact(reader.facts, "role") == role.value
            assert _fact(reader.facts, "runtime_reachable") is False
            assert _fact(reader.facts, "runtime_url") == runtime_url
            assert reader.precondition_verdict is not None, service

        # Preflight: one row per auth provider, the storage/corpus/configuration
        # rows, and the portal registry row last.
        checks = [row.check for row in projection.preflight]
        provider_checks = [f"auth-provider:{kind.value}" for kind in AuthProviderKind]
        assert checks[: len(provider_checks)] == provider_checks
        assert checks[-1] == "portal-registry:health"
        assert len(set(checks)) == len(checks)
        assert {"storage:local-root", "env:configuration"} <= set(checks)
        storage_root = next(row for row in projection.preflight if row.check == "storage:local-root")
        assert storage_root.healthy is True

        # Issues name each enabled capability whose supporting layer refuses.
        enabled = {row.capability: row.enabled for row in projection.capabilities}
        expected_issues: list[str] = []
        if enabled[ServiceCapability.LLM_VISION]:
            expected_issues.append(local_reader_service(ModelRole.VISION_TRANSCRIPTION))
        if enabled[ServiceCapability.GOOGLE_EXPORT] and not by_service[_GOOGLE_EXTRA].available:
            expected_issues.append(_GOOGLE_EXTRA)
        if enabled[ServiceCapability.CLOUD_EVIDENCE_UPLOAD] and not cloud_upload_permitted:
            expected_issues.append(_CLOUD_PERMISSION_ISSUE)
        assert list(projection.issues) == expected_issues

        # The projection restores every canonical row without loss.
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
            # The report only reads; the executor publishes NONE before probing.
            OperationEffect.NONE,
            (WORKSTATION_CHECK_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
    # The reader and contention probes call the local model runtime.
    closes_model_runtime=True,
)
