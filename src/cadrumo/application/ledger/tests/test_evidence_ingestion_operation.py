"""Canonical ingestion rows, concrete write effects and exact human authorization."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva.classification import InvoiceKind
from ...modelo.tests.m036_operation_support import PROFILE_ID as POLICY_PROFILE_ID
from ...modelo.tests.m036_operation_support import policy_decision
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.operation_definition import OperationDefinition
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
from ..batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    InferencePause,
    UnresolvedBatchSource,
    batch_item_identity,
    summarise_batch,
)
from ..evidence_ingestion_contracts import (
    LedgerEvidenceBatchExecutionResult,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
)
from ..evidence_ingestion_operation import (
    build_ledger_evidence_ingestion_definitions,
    build_ledger_evidence_ingestion_registrations,
    project_ledger_evidence_ingestion_result,
)
from ..invoice_draft_records import LabelReadingFallback, LabelReadingFallbackCause
from ..preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from .bulk_classify_operation_support import PROFILE_ID
from .evidence_ingestion_operation_support import Subject, unused

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation) -> Iterator[Subject]:
    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        yield Subject(authority_operation)


def _definition(subject: Subject) -> OperationDefinition:
    (definition,) = build_ledger_evidence_ingestion_definitions(subject.compose)
    return definition


def _run(subject: Subject, payload: BaseModel) -> None:
    definition = _definition(subject)
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID)), payload=payload
    )
    asyncio.run(definition.executor_factory.create().execute(request, subject.context(definition.definition_id)))


def test_the_real_public_contract_compiles(subject: Subject) -> None:
    definitions = build_ledger_evidence_ingestion_definitions(subject.compose)
    registrations = build_ledger_evidence_ingestion_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert tuple(row.definition_id for row in definitions) == ("ledger.evidence.batch",)
    for definition in definitions:
        assert registry.lookup_public_registration(definition.definition_id).contract.result_schema is not None
        assert definition.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
        assert OperationEffect.UNKNOWN in definition.capabilities.permitted_effects
        assert definition.capabilities.request_storage.value == "secure_reference"


def test_batch_snapshot_restores_all_rows_and_canonical_precondition_facts() -> None:
    verdict = ledger_no_recovery_verdict(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE,
        facts={"reader_available": False, "count": 0, "reader": "synthetic"},
    )
    cases: tuple[tuple[str, BatchItemStatus], ...] = (
        ("a", "ingested"),
        ("b", "no_op"),
        ("c", "refused"),
        ("d", "pending_review"),
        ("e", "paused"),
    )
    rows = tuple(
        BatchItemResult(
            content_address=letter * 64,
            identity=batch_item_identity(content_address=letter * 64, direction=InvoiceKind.RECEIVED),
            direction=InvoiceKind.RECEIVED,
            source_name=f"{letter}.pdf",
            status=status,
            refusal_code="not_readable" if status == "refused" else None,
            refusal_verdict=verdict if status == "refused" else None,
            needed_inference=letter != "a",
            label_reading_fallback=(
                LabelReadingFallback(
                    cause=LabelReadingFallbackCause.INFERENCE_SLOT_BUSY,
                    unread_fields=("supplier_name",),
                    reader_error_type="LLMBusyError",
                    failed_condition_id="llm.local_inference.slot_available",
                )
                if status == "no_op"
                else None
            ),
        )
        for letter, status in cases
    )
    run = summarise_batch(
        rows,
        (
            UnresolvedBatchSource(
                source_name="missing/file.pdf", refusal_code="unreadable_source", refusal_verdict=verdict
            ),
        ),
        InferencePause(facts={"reader_available": False, "count": 0}, precondition_verdict=verdict),
    )
    snapshot = LedgerEvidenceBatchSnapshot.from_run(run)
    restored = LedgerEvidenceBatchSnapshot.model_validate_json(snapshot.model_dump_json()).to_run()
    assert restored.model_dump(mode="json") == run.model_dump(mode="json")
    assert restored.items[1].label_reading_fallback == rows[1].label_reading_fallback
    assert restored.summary == run.summary and restored.any_failed and restored.any_deferred


def test_batch_unreadable_source_preserves_none_and_complete_refusal(subject: Subject, tmp_path: Path) -> None:
    _run(
        subject,
        LedgerEvidenceBatchRequest(
            profile_id=PROFILE_ID,
            sources=("missing.pdf",),
            source_directory=str(tmp_path),
            direction=InvoiceKind.RECEIVED,
        ),
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidenceBatchExecutionResult)
    assert result.projection.effect is OperationEffect.NONE and result.projection.write_count == 0
    assert result.projection.run.to_run().unresolved[0].source_name == "missing.pdf"
    assert not subject.store.blobs and not subject.evidence.rows


@pytest.mark.parametrize("source", ["invoice.pdf", "documents"])
def test_batch_relative_sources_keep_breadcrumbs_with_different_worker_cwd(
    subject: Subject,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    original = tmp_path / "frontend"
    directory = original / "documents"
    directory.mkdir(parents=True)
    path = directory / "invoice.pdf" if source == "documents" else original / "invoice.pdf"
    path.write_bytes(b"synthetic structured invoice bytes")
    worker = tmp_path / "worker"
    worker.mkdir()
    monkeypatch.chdir(worker)
    _run(
        subject,
        LedgerEvidenceBatchRequest(
            profile_id=PROFILE_ID, sources=(source,), source_directory=str(original), direction=InvoiceKind.RECEIVED
        ),
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidenceBatchExecutionResult)
    assert result.projection.effect is OperationEffect.PARTIAL and result.projection.write_count == 3
    assert result.projection.run.to_run().items[0].refusal_code == "not_readable"
    assert result.projection.run.items[0].source_name == "invoice.pdf"
    expected_path = str(Path(source) / "invoice.pdf") if source == "documents" else "invoice.pdf"
    assert subject.evidence.rows[0].source_path == expected_path
    assert len(subject.shared_events.load().events) == 1 and not subject.drafts.document


def test_changed_planned_source_refuses_before_any_custody_write(subject: Subject, tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"original synthetic bytes")
    subject.change_source = path
    _run(
        subject,
        LedgerEvidenceBatchRequest(
            profile_id=PROFILE_ID, sources=(str(path),), source_directory=str(tmp_path), direction=InvoiceKind.RECEIVED
        ),
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidenceBatchExecutionResult)
    assert result.projection.effect is OperationEffect.NONE and result.projection.write_count == 0
    assert result.projection.run.items[0].refusal_code == "evidence_refused"
    assert not subject.store.blobs and not subject.evidence.rows


def test_complete_batch_tracks_draft_then_replay_manifest_even_when_row_is_no_op(
    subject: Subject, tmp_path: Path
) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"synthetic structured invoice bytes")
    subject.structured_refuses = False
    request = LedgerEvidenceBatchRequest(
        profile_id=PROFILE_ID, sources=(str(path),), source_directory=str(tmp_path), direction=InvoiceKind.RECEIVED
    )
    _run(subject, request)
    first = subject.operands.values[0]
    assert isinstance(first, LedgerEvidenceBatchExecutionResult)
    assert first.projection.effect is OperationEffect.UPDATED and first.projection.write_count == 4
    assert subject.drafts.document is not None and len(subject.drafts.document.drafts) == 1
    assert not first.projection.run.to_run().any_failed
    _run(subject, request)
    second = subject.operands.values[1]
    assert isinstance(second, LedgerEvidenceBatchExecutionResult)
    assert second.projection.run.items[0].status == "no_op"
    assert second.projection.effect is OperationEffect.UPDATED and second.projection.write_count == 1
    assert len(subject.shared_events.load().events) == 1


def test_batch_swallowed_reader_revocation_still_refuses_and_retains_partial(subject: Subject, tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"synthetic structured invoice bytes")
    subject.revoke_reader = True
    with pytest.raises(ProfileAccessRefusedError):
        _run(
            subject,
            LedgerEvidenceBatchRequest(
                profile_id=PROFILE_ID,
                sources=(str(path),),
                source_directory=str(tmp_path),
                direction=InvoiceKind.RECEIVED,
            ),
        )
    assert subject.effects.effects[-1] is OperationEffect.PARTIAL
    assert len(subject.evidence.rows) == 1 and not subject.operands.values and not subject.drafts.document


def test_foreign_profile_refuses_before_composition(subject: Subject, tmp_path: Path) -> None:
    with pytest.raises(ProfileAccessRefusedError):
        _run(
            subject,
            LedgerEvidenceBatchRequest(
                profile_id=uuid4(),
                sources=("private.pdf",),
                source_directory=str(tmp_path),
                direction=InvoiceKind.RECEIVED,
            ),
        )
    assert subject.before_read is unused and not subject.operands.values


def test_exact_human_all_period_dual_disclosure_policy(subject: Subject, tmp_path: Path) -> None:
    definitions = build_ledger_evidence_ingestion_definitions(subject.compose)
    registrations = build_ledger_evidence_ingestion_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    registration = registry.lookup_public_registration("ledger.evidence.batch")
    payload = LedgerEvidenceBatchRequest(
        profile_id=POLICY_PROFILE_ID,
        sources=("private.pdf",),
        source_directory=str(tmp_path),
        direction=InvoiceKind.RECEIVED,
    )
    request = OperationRequest[BaseModel](
        definition_id="ledger.evidence.batch",
        subject_ref=profile_operation_subject(str(POLICY_PROFILE_ID)),
        payload=payload,
    )
    context = OperationAccessContext(
        profile_id=POLICY_PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.RESULT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=subject.operation,
    )
    resolved = resolve_operation_access(registry=registry, request=request, context=context)
    assert resolved.policy.requires_human and resolved.policy.requires_all_periods
    assert {row.category for row in resolved.policy.disclosures} == {
        DisclosureCategory.PROFILE_VALUES,
        DisclosureCategory.TAX_VALUES,
    }
    assert isinstance(
        policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True), AccessAllowed
    )
    assert isinstance(policy_decision(resolved, registry, disclosures=resolved.policy.disclosures), AccessDenied)
    assert isinstance(
        policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True, all_periods=False),
        AccessDenied,
    )
    for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES):
        assert isinstance(
            policy_decision(
                resolved,
                registry,
                human=True,
                disclosures=frozenset(row for row in resolved.policy.disclosures if row.category is not category),
            ),
            AccessDenied,
        )
    observed = resolve_operation_access(
        registry=registry, request=request, context=replace(context, action=AccessAction.OBSERVE)
    )
    assert {row.category for row in observed.policy.disclosures} == {DisclosureCategory.OPERATION_METADATA}
    with pytest.raises(ProfileAccessRefusedError):
        resolve_operation_access(
            registry=registry, request=request, context=replace(context, frontend=OperationFrontendProjection.MCP)
        )


def test_projection_rejects_terminal_effect_that_hides_real_writes(subject: Subject, tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"synthetic structured invoice bytes")
    subject.structured_refuses = False
    _run(
        subject,
        LedgerEvidenceBatchRequest(
            profile_id=PROFILE_ID, sources=(str(path),), source_directory=str(tmp_path), direction=InvoiceKind.RECEIVED
        ),
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidenceBatchExecutionResult)
    assert result.projection.effect is OperationEffect.UPDATED
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id="ledger.evidence.batch",
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        ),
        revision=1,
        settled_at=now(),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        result_ref="d" * 64,
    )
    with pytest.raises(ValueError, match="contradicts"):
        project_ledger_evidence_ingestion_result(result, receipt)
    assert (
        project_ledger_evidence_ingestion_result(result, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))
        == result.projection
    )


def test_batch_with_a_custody_write_of_unknown_outcome_refuses_and_reports_unknown(
    subject: Subject, tmp_path: Path
) -> None:
    """The batch absorbs the failed row, so the uncertainty has to be raised as the operation's refusal."""
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"synthetic structured invoice bytes")
    subject.structured_refuses = False
    # The writer stores the bytes and then loses the acknowledgement: nothing can
    # say whether the write is durable.
    subject.store.fail_after_blob_write = True

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _run(
            subject,
            LedgerEvidenceBatchRequest(
                profile_id=PROFILE_ID,
                sources=(str(path),),
                source_directory=str(tmp_path),
                direction=InvoiceKind.RECEIVED,
            ),
        )

    assert refused.value.code.code == "REFUSED_PROFILE_ACCESS"
    assert refused.value.reason is AccessDenialCode.OPERATION_DENIED
    assert subject.effects.effects[-1] is OperationEffect.UNKNOWN
    assert not subject.operands.values


def test_a_batch_result_document_cannot_claim_an_uncertain_effect() -> None:
    """The refusal above exists because a stored result describes certain writes only."""
    with pytest.raises(ValidationError, match="certain concrete writer outcomes"):
        LedgerEvidenceBatchProjection(
            profile_id=PROFILE_ID,
            direction=InvoiceKind.RECEIVED,
            run=LedgerEvidenceBatchSnapshot(items=(), unresolved=(), inference_pause=None),
            write_count=1,
            effect=OperationEffect.UNKNOWN,
        )
