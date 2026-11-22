"""Registered-executor conformance scenarios for checking, probing and releasing purchase evidence."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from ...application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_kind_proposal import derived_evidence_kind
from ...application.ledger.evidence_probe_operation import (
    LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
    LedgerEvidenceProbeProjection,
    LedgerEvidenceProbeRequest,
)
from ...application.ledger.evidence_verify_operation import (
    LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
    LedgerEvidenceVerifyChecked,
    LedgerEvidenceVerifyProjection,
    LedgerEvidenceVerifyRequest,
)
from ...application.ledger.manual_update import attach_manual_transaction_evidence
from ...application.ledger.purchase_evidence_release_operation import (
    LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
    LedgerPurchaseEvidenceReleaseRequest,
    LedgerPurchaseEvidenceReleaseResult,
)
from ...core.document_shape import DocumentShape
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..adapter_composition_work_ports import build_ledger_evidence_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import SEED_ACTOR, ledger_action_ports, seed_manual_transaction

_FACTURAE_NAME = "facturae_32_series_and_parties_invoice.xml"
_FACTURAE_CORPUS = Path(__file__).parents[2] / "application" / "ledger" / "tests" / "_evidence_corpus" / _FACTURAE_NAME


def _new_events(context: ConformanceFamilyContext, before_ids: frozenset[str]) -> tuple[BucketEvent, ...]:
    events = ledger_action_ports(context).bucket_event_repository.load().events
    return tuple(event for event_id, event in events.items() if event_id not in before_ids)


def _stored_pdf_evidence(context: ConformanceFamilyContext, name: str) -> PurchaseInvoiceEvidence:
    """Store one synthetic text PDF as purchase evidence through the production add path."""
    bucket_id = str(context.profile_id)
    source = context.input_root / name
    source.write_bytes(multi_page_text_pdf_bytes(("Conformance purchase invoice",)))
    return (
        PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id))
        .add(bucket_id=bucket_id, source_path=source)
        .record
    )


def _prepare_verify(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)
    record = _stored_pdf_evidence(context, "conformance-verify-evidence.pdf")
    events_before = frozenset(ledger_action_ports(context).bucket_event_repository.load().events)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(LedgerEvidenceVerifyProjection)
        assert projection.profile_id == context.profile_id
        checked = projection.outcome
        assert isinstance(checked, LedgerEvidenceVerifyChecked)
        assert checked.record.evidence_id == record.evidence_id
        assert checked.record.attachment_id == record.attachment_id
        # A text PDF is recognised by the shape probe, so the kept finding is readable.
        # evidence_verify_operation.py `_check_evidence_readability`.
        assert checked.record.readability == "readable"
        assert checked.record.document_shape is DocumentShape.PDF_TEXT_LAYER
        assert checked.record.unreadable_cause is None

        kept = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id)).view(
            bucket_id=bucket_id, evidence_id=record.evidence_id
        )
        assert kept.readability is not None and kept.readability.state == "readable"
        assert kept.readability.checked_sha256 == record.attachment_id

        new_events = _new_events(context, events_before)
        assert len(new_events) == 1
        event = new_events[0]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
        assert event.object_id == record.evidence_id
        assert event.payload["mutation_kind"] == "readability_checked"
        assert checked.bucket_event_ids == (event.event_id,)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerEvidenceVerifyRequest(profile_id=context.profile_id, evidence_id=record.evidence_id),
        verify=verify,
    )


def _prepare_probe(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)
    source = context.input_root / _FACTURAE_NAME
    source.write_bytes(_FACTURAE_CORPUS.read_bytes())
    ports = ledger_action_ports(context)
    events_before = ports.bucket_event_repository.load()
    evidence_before = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id)).list_all(
        bucket_id=bucket_id
    )

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(LedgerEvidenceProbeProjection)
        assert projection.profile_id == context.profile_id
        # A standalone Facturae file carries a structured record, so its kind is offered.
        # evidence_probe_operation.py `LedgerEvidenceProbeExecutor`.
        assert projection.document_shape is DocumentShape.XML_FACTURAE
        assert projection.kind_proposal is not None
        assert projection.kind_proposal == derived_evidence_kind(DocumentShape.XML_FACTURAE)
        released = projection.model_dump_json()
        assert str(context.input_root) not in released
        # The probe stores nothing: no evidence record and no event.
        after = ledger_action_ports(context)
        assert after.bucket_event_repository.load() == events_before
        assert (
            PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id)).list_all(
                bucket_id=bucket_id
            )
            == evidence_before
        )

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerEvidenceProbeRequest(
            profile_id=context.profile_id, source_path=str(source), source_directory=str(context.input_root)
        ),
        verify=verify,
    )


def _prepare_release(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)
    transaction_id = seed_manual_transaction(
        context,
        booked_date=date(filing_year_envelope().horizon, 5, 1),
        amount=Decimal("121.00"),
        description="evidence release row",
    )
    record = _stored_pdf_evidence(context, "conformance-release-evidence.pdf")
    ports = ledger_action_ports(context)
    attach_manual_transaction_evidence(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        actor=SEED_ACTOR,
        purchase_invoice_evidence_id=record.evidence_id,
        ports=ports,
    )
    evidenced = ports.transaction_repository.load().get(transaction_id)
    assert evidenced is not None
    assert evidenced.purchase_invoice_evidence_id == record.evidence_id
    assert record.attachment_id not in evidenced.attachment_ids
    events_before = frozenset(ports.bucket_event_repository.load().events)

    def verify(outcome: ConformanceOutcome) -> None:
        after = ledger_action_ports(context)
        # Kept as a document: the slot is cleared and the evidence's stored bytes stay
        # on the movement as an ordinary attachment. purchase_evidence_release.py.
        transaction = after.transaction_repository.load().get(transaction_id)
        assert transaction is not None
        assert transaction.purchase_invoice_evidence_id is None
        assert transaction.attachment_ids == (record.attachment_id,)
        assert after.attachment_store.read_bytes(record.attachment_id)

        new_events = _new_events(context, events_before)
        assert {event.event_type for event in new_events} == {
            BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
            BucketEventType.ATTACHMENT_LINKED,
        }

        result = outcome.resolve_result(LedgerPurchaseEvidenceReleaseResult)
        assert result.outcome == "updated" and result.refusal is None
        assert result.profile_id == context.profile_id
        assert result.disposition == "keep_as_document"
        assert result.released_evidence_id == record.evidence_id
        assert result.transaction is not None
        assert result.transaction.transaction_id == transaction_id
        assert set(result.bucket_event_ids) == {event.event_id for event in new_events}

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=LedgerPurchaseEvidenceReleaseRequest(
            profile_id=context.profile_id,
            transaction_id=transaction_id[:12],
            expected_purchase_invoice_evidence_id=record.evidence_id,
            expected_modified_at=evidenced.modified_at.isoformat(),
            disposition="keep_as_document",
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID:
        return _prepare_verify(context)
    if definition_id == LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID:
        return _prepare_probe(context)
    if definition_id == LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID:
        return _prepare_release(context)
    raise AssertionError(f"no ledger evidence check conformance scenario for {definition_id}")


LEDGER_EVIDENCE_CHECK_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Each publishes the single phase named after the definition. The check and the
        # release persist a bucket event and settle UPDATED; the probe stores nothing and
        # settles NONE. evidence_verify_operation.py, evidence_probe_operation.py,
        # purchase_evidence_release_operation.py.
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LEDGER_EVIDENCE_PROBE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
