"""Canonical ingestion rows, concrete write effects and exact human authorization."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ....core.config import override_settings
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.time.clock import now
from ....domain.attachments.enums import DocumentLinkSource
from ....domain.attachments.errors import AttachmentValidationError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva.classification import InvoiceKind
from ...modelo.tests.m036_operation_support import PROFILE_ID as POLICY_PROFILE_ID
from ...modelo.tests.m036_operation_support import policy_decision
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.operation_definition import OperationDefinition
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessAllowed, AccessDenied, Availability, DisclosureCategory
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..batch_ingest import (
    BatchItemResult,
    BatchItemStatus,
    InferencePause,
    UnresolvedBatchSource,
    batch_item_identity,
    summarise_batch,
)
from ..evidence_ingestion_operation import (
    LedgerEvidenceBatchExecutionResult,
    LedgerEvidenceBatchRequest,
    LedgerEvidenceBatchSnapshot,
    LedgerEvidencePullAllExecutionResult,
    LedgerEvidencePullAllRequest,
    LedgerEvidencePullExecutionResult,
    LedgerEvidencePullRequest,
    build_ledger_evidence_ingestion_definitions,
    build_ledger_evidence_ingestion_registrations,
    project_ledger_evidence_ingestion_result,
)
from ..evidence_sweep_ports import EvidenceSweepDocument
from ..invoice_draft_records import LabelReadingFallback, LabelReadingFallbackCause
from ..persistence_ports import LedgerPersistenceConflictError
from ..preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from .bulk_classify_operation_support import PROFILE_ID
from .evidence_ingestion_operation_support import Subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def subject(authority_operation: PinnedAuthorityOperation) -> Iterator[Subject]:
    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        yield Subject(authority_operation)


def _definition(subject: Subject, kind: str) -> OperationDefinition:
    return next(
        row
        for row in build_ledger_evidence_ingestion_definitions(subject.compose)
        if row.definition_id == "ledger.evidence." + kind
    )


def _run(subject: Subject, payload: BaseModel, kind: str) -> None:
    definition = _definition(subject, kind)
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID)), payload=payload
    )
    asyncio.run(definition.executor_factory.create().execute(request, subject.context(definition.definition_id)))


def test_all_three_real_public_contracts_compile(subject: Subject) -> None:
    definitions = build_ledger_evidence_ingestion_definitions(subject.compose)
    registrations = build_ledger_evidence_ingestion_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    assert tuple(row.definition_id for row in definitions) == (
        "ledger.evidence.batch",
        "ledger.evidence.pull",
        "ledger.evidence.pull_all",
    )
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
        "batch",
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
        "batch",
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
        "batch",
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
    _run(subject, request, "batch")
    first = subject.operands.values[0]
    assert isinstance(first, LedgerEvidenceBatchExecutionResult)
    assert first.projection.effect is OperationEffect.UPDATED and first.projection.write_count == 4
    assert subject.drafts.document is not None and len(subject.drafts.document.drafts) == 1
    assert not first.projection.run.to_run().any_failed
    _run(subject, request, "batch")
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
            "batch",
        )
    assert subject.effects.effects[-1] is OperationEffect.PARTIAL
    assert len(subject.evidence.rows) == 1 and not subject.operands.values and not subject.drafts.document


def test_single_pull_preserves_full_mutation_and_separate_real_writer_count(subject: Subject) -> None:
    _run(
        subject,
        LedgerEvidencePullRequest(
            profile_id=PROFILE_ID,
            transaction_id=subject.transaction.transaction_id[:12],
            source=DocumentLinkSource.GOOGLE_DRIVE,
            reference="synthetic-drive-document",
            note="retained human note",
        ),
        "pull",
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidencePullExecutionResult)
    projection = result.projection
    # Blob and manifest are separate; transaction and event share one co-commit.
    assert projection.effect is OperationEffect.UPDATED and projection.write_count == 3
    assert projection.bucket_event_ids and projection.transaction.transaction_id == projection.transaction_id
    assert (
        projection.transaction.attachment_ids
        and projection.requested_transaction_id == subject.transaction.transaction_id[:12]
    )
    assert subject.store.manifests[projection.transaction.attachment_ids[0]].notes == "retained human note"
    assert not subject.fence.active


def test_folder_sweep_retains_order_skipped_and_individual_scope_refusal(subject: Subject) -> None:
    subject.acquisition.refused.add(subject.acquisition.documents[1].file_id)
    _run(
        subject,
        LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder", note="human note"),
        "pull_all",
    )
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidencePullAllExecutionResult)
    projection = result.projection
    assert tuple(row.file_id for row in projection.files) == tuple(
        document.file_id for document in subject.acquisition.documents
    )
    assert (
        projection.total_documents,
        projection.fetched_count,
        projection.refused_count,
        projection.skipped_non_document_count,
    ) == (2, 1, 1, 3)
    assert projection.files[1].refusal_reason is not None
    assert projection.effect is OperationEffect.PARTIAL and projection.write_count == 2


def test_folder_sweep_persists_canonical_url_context_ids(subject: Subject) -> None:
    """Application provenance accepts complete provider IDs of URL-context lengths."""
    subject.acquisition.documents = (
        EvidenceSweepDocument("A" * 10, "Ten.pdf", "application/pdf"),
        EvidenceSweepDocument("B" * 24, "Twenty-four.pdf", "application/pdf"),
    )

    _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")

    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidencePullAllExecutionResult)
    for row in result.projection.files:
        assert row.fetched and row.attachment_id is not None
        attachment = subject.store.manifests[row.attachment_id]
        assert attachment.source_reference == f"https://drive.google.com/file/d/{row.file_id}"


@pytest.mark.parametrize("file_id", ("A" * 9, "A" * 10 + "!"))
def test_folder_sweep_rejects_malformed_provider_id_before_fetch_or_write(subject: Subject, file_id: str) -> None:
    """An unconstrained acquisition port cannot pass an invalid ID to fetch or custody."""
    subject.acquisition.documents = (EvidenceSweepDocument(file_id, "Invalid.pdf", "application/pdf"),)

    with pytest.raises(AttachmentValidationError, match="invalid file ID"):
        _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")

    assert subject.acquisition.calls == ["human-folder"]
    assert not subject.store.blobs and not subject.store.manifests


@pytest.mark.parametrize(
    ("mode", "effect"), [("conflict", OperationEffect.PARTIAL), ("uncertain", OperationEffect.UNKNOWN)]
)
def test_pull_opened_row_cas_preserves_prior_custody_effect(
    subject: Subject, mode: str, effect: OperationEffect
) -> None:
    """A denied row CAS follows confirmed custody; an uncertain commit stays unknown."""
    subject.transactions.mode = mode
    with pytest.raises((LedgerPersistenceConflictError, OSError)):
        _run(
            subject,
            LedgerEvidencePullRequest(
                profile_id=PROFILE_ID,
                transaction_id=subject.transaction.transaction_id[:12],
                source=DocumentLinkSource.GOOGLE_DRIVE,
                reference="synthetic-drive-document",
            ),
            "pull",
        )
    assert subject.effects.effects[-1] is effect and subject.store.blobs
    assert not subject.operands.values and not subject.fence.active


def test_folder_all_refused_succeeds_without_local_mutations(subject: Subject) -> None:
    subject.acquisition.refused.update(document.file_id for document in subject.acquisition.documents)
    _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidencePullAllExecutionResult)
    assert result.projection.effect is OperationEffect.NONE and result.projection.write_count == 0
    assert result.projection.refused_count == 2 and not subject.store.blobs


@pytest.mark.parametrize(
    ("mode", "effect"), [("preparation", OperationEffect.PARTIAL), ("uncertain", OperationEffect.UNKNOWN)]
)
def test_actual_blob_then_failure_preserves_partial_or_unknown(
    subject: Subject, mode: str, effect: OperationEffect
) -> None:
    subject.store.fail_manifest_preparation = mode == "preparation"
    subject.store.fail_after_blob_write = mode == "uncertain"
    with pytest.raises((ValueError, OSError)):
        _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")
    assert subject.effects.effects[-1] is effect and subject.store.blobs
    assert not subject.operands.values and not subject.fence.active


def test_folder_authority_revocation_stops_after_prior_confirmed_custody(subject: Subject) -> None:
    subject.acquisition.revoke_after_first = True
    with pytest.raises(ProfileAccessRefusedError):
        _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")
    assert subject.effects.effects[-1] is OperationEffect.PARTIAL
    assert len(subject.store.blobs) == 1 and not subject.operands.values and not subject.fence.active


def test_foreign_profile_refuses_before_composition(subject: Subject) -> None:
    with pytest.raises(ProfileAccessRefusedError):
        _run(subject, LedgerEvidencePullAllRequest(profile_id=uuid4(), folder="private-folder"), "pull_all")
    assert not subject.acquisition.calls and not subject.operands.values


@pytest.mark.parametrize("kind", ["batch", "pull", "pull_all"])
def test_exact_human_all_period_dual_disclosure_policy(subject: Subject, tmp_path: Path, kind: str) -> None:
    definitions = build_ledger_evidence_ingestion_definitions(subject.compose)
    registrations = build_ledger_evidence_ingestion_registrations(definitions)
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    registration = registry.lookup_public_registration("ledger.evidence." + kind)
    payload: BaseModel
    if kind == "batch":
        payload = LedgerEvidenceBatchRequest(
            profile_id=POLICY_PROFILE_ID,
            sources=("private.pdf",),
            source_directory=str(tmp_path),
            direction=InvoiceKind.RECEIVED,
        )
    elif kind == "pull":
        payload = LedgerEvidencePullRequest(
            profile_id=POLICY_PROFILE_ID,
            transaction_id=subject.transaction.transaction_id,
            source=DocumentLinkSource.GOOGLE_DRIVE,
            reference="private-ref",
        )
    else:
        payload = LedgerEvidencePullAllRequest(profile_id=POLICY_PROFILE_ID, folder="private-folder")
    request = OperationRequest[BaseModel](
        definition_id="ledger.evidence." + kind,
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


def test_projection_rejects_terminal_effect_that_hides_real_writes(subject: Subject) -> None:
    _run(subject, LedgerEvidencePullAllRequest(profile_id=PROFILE_ID, folder="human-folder"), "pull_all")
    result = subject.operands.values[0]
    assert isinstance(result, LedgerEvidencePullAllExecutionResult)
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id="ledger.evidence.pull_all",
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
