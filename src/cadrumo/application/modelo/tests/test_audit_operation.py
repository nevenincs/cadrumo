"""Canonical audit behavior, disclosure boundaries and real synthetic ZIP writes.

Inward repositories isolate application policy; filesystem artifacts are real.
These cases do not establish installed runtime or native encrypted-storage acceptance.
"""

from __future__ import annotations

import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...evidence import service as service_module
from ...evidence.models import (
    BundleVerificationState,
    EvidenceBundleNotFoundError,
    EvidenceBundleVerificationError,
    VerificationCheck,
)
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext
from ...operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import audit_operation as module
from ..audit_operation_ports import ModeloAuditOperationPorts
from .audit_operation_support import NOTE, SOURCE_ADDRESS, Subject
from .m036_operation_support import INSTANT, PROFILE_ID, policy_decision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch) -> Subject:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(PROFILE_ID))
    return Subject(authority_operation)


def _registry(subject: Subject) -> OperationRegistry:
    definitions = module.build_modelo_audit_operation_definitions(subject.compose_audit)
    return OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda row: row.definition_id)),
        public_registrations=tuple(
            sorted(
                module.build_modelo_audit_operation_registrations(definitions),
                key=lambda row: row.contract.definition_id,
            )
        ),
    )


def _read_request(
    subject: Subject, *, kind: module.ModeloAuditReadKind, query: bool = False, bundle_id: str | None = None
) -> OperationRequest[module.ModeloAuditReadRequest]:
    return OperationRequest[module.ModeloAuditReadRequest](
        definition_id=module.MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID
        if query
        else module.MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.ModeloAuditReadRequest(
            profile_id=PROFILE_ID, kind=kind, bundle_id=subject.bundle.bundle_id if bundle_id is None else bundle_id
        ),
    )


def _export_request(
    subject: Subject, output: Path, *, force: bool = False
) -> OperationRequest[module.ModeloAuditExportRequest]:
    return OperationRequest[module.ModeloAuditExportRequest](
        definition_id=module.MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.ModeloAuditExportRequest(
            profile_id=PROFILE_ID, bundle_id=subject.bundle.bundle_id, output=output, force_incomplete=force
        ),
    )


def test_real_registry_compiles_all_purpose_schemas_without_agent_source_prose(subject: Subject) -> None:
    registry = _registry(subject)
    for definition in module.build_modelo_audit_operation_definitions(subject.compose_audit):
        contract = registry.lookup_public_contract(definition.definition_id)
        assert contract.request_schema is not None and contract.result_schema is not None
        assert contract.result_schema.schema_id == definition.definition_id + ".result"
        assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects
    assert "notes" in module.ModeloAuditBundleSnapshot.model_fields
    assert "notes" not in module.ModeloAuditQueryBundle.model_fields
    assert "object_id" not in module.ModeloAuditQueryRecord.model_fields
    assert "detail" not in module.ModeloAuditQueryFinding.model_fields
    assert registry.lookup(module.MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID).permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI}
    )


@pytest.mark.asyncio
async def test_full_view_preserves_canonical_manifest_and_query_removes_raw_addresses(subject: Subject) -> None:
    for query in (False, True):
        request = _read_request(subject, kind="view", query=query, bundle_id=subject.bundle.bundle_id[:12])
        await module.ModeloAuditReadExecutor(subject.compose_audit, query=query).execute(
            request, subject.context(request.definition_id)
        )
    human = cast(module.ModeloAuditReadExecutionResult, subject.operands.values[-2]).projection
    agent = cast(module.ModeloAuditQueryExecutionResult, subject.operands.values[-1]).projection
    assert human.bundle is not None and human.bundle.to_bundle() == subject.bundle
    assert human.bundle.to_bundle().model_dump(mode="json") == subject.bundle.model_dump(mode="json")
    assert agent.bundle is not None and agent.bundle.bucket_id == str(PROFILE_ID)
    assert agent.bundle.bundle_id == subject.bundle.bundle_id and agent.bundle.notes_present
    assert agent.bundle.records[0].content_sha256 == subject.bundle.records[0].content_sha256
    assert agent.bundle.records[0].payload_size_bytes == subject.bundle.records[0].payload_size_bytes
    assert NOTE not in agent.model_dump_json() and SOURCE_ADDRESS not in agent.model_dump_json()
    assert subject.events.effects[-1] is OperationEffect.NONE
    assert subject.evidence_repository.writes == subject.fence.entries == 0


@pytest.mark.asyncio
async def test_check_reuses_default_unreachable_semantics_and_complete_ordered_findings(subject: Subject) -> None:
    expected = subject.service.check(bucket_id=str(PROFILE_ID), bundle_id=subject.bundle.bundle_id)
    for query in (False, True):
        request = _read_request(subject, kind="check", query=query)
        await module.ModeloAuditReadExecutor(subject.compose_audit, query=query).execute(
            request, subject.context(request.definition_id)
        )
    human = cast(module.ModeloAuditReadExecutionResult, subject.operands.values[-2]).projection
    agent = cast(module.ModeloAuditQueryExecutionResult, subject.operands.values[-1]).projection
    assert human.report is not None and human.report.to_report() == expected
    assert human.report.to_report().model_dump(mode="json") == expected.model_dump(mode="json")
    assert expected.verification_state is BundleVerificationState.INCOMPLETE and expected.completeness_ratio == 0.0
    assert agent.report is not None and agent.report.verification_state == expected.verification_state
    assert tuple((row.check, row.passed) for row in agent.report.findings) == tuple(
        (row.check, row.passed) for row in expected.findings
    )
    reachability = next(row for row in agent.report.findings if row.check is VerificationCheck.OBJECT_REACHABILITY)
    assert not reachability.passed and subject.evidence_repository.writes == 0


@pytest.mark.asyncio
async def test_force_export_preserves_zip_manifest_receipt_and_actual_writer_scope(
    subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_zip_file = zipfile.ZipFile

    def archive_writer(file: Path, *, mode: Literal["w"], compression: int) -> zipfile.ZipFile:
        assert subject.fence.active, "canonical ZIP I/O requires operation write authority"
        return original_zip_file(file, mode=mode, compression=compression)

    monkeypatch.setattr(service_module.zipfile, "ZipFile", archive_writer)
    output = tmp_path / "new-parent" / "audit.zip"
    request = _export_request(subject, output, force=True)
    await module.ModeloAuditExportExecutor(subject.compose_audit).execute(
        request, subject.context(request.definition_id)
    )
    projection = cast(module.ModeloAuditExportExecutionResult, subject.operands.values[-1]).projection
    assert projection.profile_id == PROFILE_ID and projection.output == str(output)
    assert projection.records == len(subject.bundle.records)
    assert projection.verification_state is subject.bundle.verification_state
    with original_zip_file(output) as archive:
        assert archive.namelist() == ["manifest.json"]
        assert archive.read("manifest.json") == subject.bundle.model_dump_json(indent=2).encode("utf-8")
    assert subject.events.effects[-1] is OperationEffect.UPDATED
    assert subject.fence.entries == 1 and not subject.fence.active
    assert subject.evidence_repository.writes == 0
    assert all(NOTE not in value and str(output) not in value for value in subject.events.phases)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_verification_refuses_before_output_and_force_never_overrides_failed(
    subject: Subject, tmp_path: Path, failed: bool
) -> None:
    if failed:
        subject.bundle = subject.bundle.model_copy(update={"bundle_id": "d" * 64})
        subject.evidence_repository.bundles = {subject.bundle.bundle_id: subject.bundle}
    output = tmp_path / "uncreated" / "audit.zip"
    request = _export_request(subject, output, force=failed)
    with pytest.raises(EvidenceBundleVerificationError):
        await module.ModeloAuditExportExecutor(subject.compose_audit).execute(
            request, subject.context(request.definition_id)
        )
    assert not output.parent.exists() and subject.fence.entries == 0
    assert subject.events.effects[-1] is OperationEffect.NONE and not subject.operands.values


@pytest.mark.asyncio
@pytest.mark.parametrize("after_close", [False, True])
async def test_denied_writer_and_actual_closed_zip_failure_have_distinct_effects(
    subject: Subject, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_close: bool
) -> None:
    original_zip_file = zipfile.ZipFile

    class FailingCloseArchive(zipfile.ZipFile):
        @override
        def close(self) -> None:
            opened = self.fp is not None
            super().close()
            if opened:
                assert subject.fence.active
                raise OSError("synthetic failure after actual ZIP close")

    if after_close:
        monkeypatch.setattr(service_module.zipfile, "ZipFile", FailingCloseArchive)
    else:
        subject.fence.deny = True
    output = tmp_path / "audit.zip"
    request = _export_request(subject, output, force=True)
    with pytest.raises((OSError, ProfileAccessRefusedError)):
        await module.ModeloAuditExportExecutor(subject.compose_audit).execute(
            request, subject.context(request.definition_id)
        )
    if after_close:
        with original_zip_file(output) as archive:
            assert archive.namelist() == ["manifest.json"]
    else:
        assert not output.exists()
    assert subject.events.effects[-1] is (OperationEffect.UNKNOWN if after_close else OperationEffect.NONE)
    assert not subject.operands.values and not subject.fence.active


@pytest.mark.asyncio
async def test_exact_profile_lookup_and_prefix_ambiguity_remain_canonical(subject: Subject) -> None:
    foreign = subject.bundle.model_copy(update={"bucket_id": str(uuid4()), "bundle_id": "d" * 64})
    subject.evidence_repository.bundles[foreign.bundle_id] = foreign
    request = _read_request(subject, kind="view", query=True, bundle_id=foreign.bundle_id)
    with pytest.raises(EvidenceBundleNotFoundError):
        await module.ModeloAuditReadExecutor(subject.compose_audit, query=True).execute(
            request, subject.context(request.definition_id)
        )
    for suffix in ("1", "2"):
        ambiguous = subject.bundle.model_copy(update={"bundle_id": "ab" + suffix * 62})
        subject.evidence_repository.bundles[ambiguous.bundle_id] = ambiguous
    request = _read_request(subject, kind="view", query=True, bundle_id="ab")
    with pytest.raises(EvidenceBundleNotFoundError) as caught:
        await module.ModeloAuditReadExecutor(subject.compose_audit, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert caught.value.translated_message == "errors.refused.refused_evidence_bundle_ambiguous"
    assert not subject.operands.values and subject.evidence_repository.writes == 0


@pytest.mark.asyncio
async def test_wrong_worker_identity_refuses_before_manifest_access(subject: Subject) -> None:
    wrong = replace(subject.audit_ports, profile_id=uuid4())

    def compose(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloAuditOperationPorts:
        return wrong

    request = _read_request(subject, kind="check", query=True)
    with pytest.raises(ProfileAccessRefusedError):
        await module.ModeloAuditReadExecutor(compose, query=True).execute(
            request, subject.context(request.definition_id)
        )
    assert subject.evidence_repository.reads == subject.fence.entries == 0


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_query_actual_policy_requires_complete_destination_consent_and_all_periods(
    subject: Subject, missing: DisclosureCategory | None
) -> None:
    registry = _registry(subject)
    request = _read_request(subject, kind="view", query=True)
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.MCP,
        contract=registry.lookup_public_contract(request.definition_id),
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    resolved = module.resolve_modelo_audit_operation_access(public, context)
    disclosures = frozenset(row for row in resolved.policy.disclosures if row.category is not missing)
    decision = policy_decision(resolved, registry, disclosures=disclosures)
    if missing is None:
        assert isinstance(decision, AccessAllowed)
        wrong_destination = frozenset(row.model_copy(update={"destination_id": uuid4()}) for row in disclosures)
        denied = policy_decision(resolved, registry, disclosures=wrong_destination)
        assert isinstance(denied, AccessDenied) and denied.code is AccessDenialCode.DISCLOSURE_DENIED
        restricted = policy_decision(resolved, registry, disclosures=disclosures, all_periods=False)
        assert isinstance(restricted, AccessDenied) and restricted.code is AccessDenialCode.PERIOD_DENIED
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED


def test_query_authority_cannot_authorize_human_read_export_and_observation_stays_metadata(
    subject: Subject, tmp_path: Path
) -> None:
    registry = _registry(subject)
    for request in (_read_request(subject, kind="view"), _export_request(subject, tmp_path / "audit.zip")):
        public = OperationRequest[BaseModel](
            definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
        )
        context = OperationAccessContext(
            profile_id=PROFILE_ID,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=registry.lookup_public_contract(request.definition_id),
            published_authority=Availability.AVAILABLE,
            authority_operation=subject.operation,
        )
        resolved = module.resolve_modelo_audit_operation_access(public, context)
        allowed = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True)
        assert isinstance(allowed, AccessAllowed)
        restricted = policy_decision(
            resolved,
            registry,
            disclosures=resolved.policy.disclosures,
            human=True,
            operations=frozenset({module.MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID}),
        )
        assert isinstance(restricted, AccessDenied) and restricted.code is AccessDenialCode.OPERATION_DENIED
        automated = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)
        assert isinstance(automated, AccessDenied) and automated.code is AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
        with pytest.raises(ProfileAccessRefusedError):
            module.resolve_modelo_audit_operation_access(
                public, replace(context, frontend=OperationFrontendProjection.MCP)
            )
        observed = module.resolve_modelo_audit_operation_access(public, replace(context, action=AccessAction.OBSERVE))
        permission = next(iter(observed.policy.disclosures))
        assert len(observed.policy.disclosures) == 1 and permission.category is DisclosureCategory.OPERATION_METADATA
        assert permission.projection_id == OPERATION_OBSERVATION_PROJECTION_ID
        assert (AccessAction.COMMIT in observed.policy.actions) == (
            request.definition_id == module.MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID
        )


def test_projector_requires_exact_profile_purpose_and_actual_successful_write_receipt() -> None:
    result = module.ModeloAuditExportExecutionResult(
        projection=module.ModeloAuditExportProjection(
            profile_id=PROFILE_ID,
            bundle_id="a" * 64,
            output="synthetic.zip",
            verification_state=BundleVerificationState.PENDING,
            records=1,
        )
    )
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="b" * 64,
            definition_id=module.MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=INSTANT,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        result_ref="d" * 64,
    )
    assert module.project_modelo_audit_operation_result(result, receipt) == result.projection
    for effect in (OperationEffect.NONE, OperationEffect.UNKNOWN):
        with pytest.raises(ValueError):
            module.project_modelo_audit_operation_result(result, receipt.model_copy(update={"effect": effect}))
    wrong = receipt.identity.model_copy(update={"definition_id": module.MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID})
    with pytest.raises(ValueError):
        module.project_modelo_audit_operation_result(result, receipt.model_copy(update={"identity": wrong}))
