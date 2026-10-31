"""Assert ledger and invoice operation outcomes for the registered executor conformance run."""

from __future__ import annotations

import asyncio
import csv
from collections.abc import Callable
from decimal import Decimal

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.counterparty_establishment import build_counterparty_establishment_repository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.own_accounts import OwnAccountRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.invoices.catalogue_add_contracts import InvoiceAddResult
from ...application.invoices.catalogue_read_operation import (
    INVOICE_LIST_OPERATION_DEFINITION_ID,
    INVOICE_VIEW_OPERATION_DEFINITION_ID,
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceViewProjection,
    InvoiceViewRequest,
    InvoiceViewSuccess,
)
from ...application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ...application.invoices.catalogue_remove_operation import (
    INVOICE_REMOVE_OPERATION_DEFINITION_ID,
    InvoiceRemoveRequest,
    InvoiceRemoveResult,
)
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdateRequest,
    InvoiceUpdateResult,
)
from ...application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from ...application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
)
from ...application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ...application.ledger.classify_requests import LedgerClassifyRequest
from ...application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from ...application.ledger.counterparty_operation import LedgerCounterpartyRequest, LedgerCounterpartyResult
from ...application.ledger.evidence_add_operation import LedgerEvidenceAddProjection, LedgerEvidenceAddRequest
from ...application.ledger.evidence_mutation_operation import (
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from ...application.ledger.evidence_read_operation import (
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from ...application.ledger.history_operation import LedgerHistoryProjection, LedgerHistoryRequest
from ...application.ledger.import_operation import LedgerImportRequest, LedgerImportResultProjection
from ...application.ledger.ledger_add_contracts import LedgerAddOperationResult, LedgerAddRequest
from ...application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ...application.ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from ...application.ledger.models import ManualLedgerTransactionPatch
from ...application.ledger.own_account_operation import LedgerOwnAccountRequest, LedgerOwnAccountResult
from ...application.ledger.participation_operation import LedgerParticipationRequest
from ...application.ledger.participation_rebuild_operation import LedgerParticipationRebuildRequest
from ...application.ledger.preflight import LedgerPreflightIssueReason
from ...application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from ...application.ledger.remove_operation import LedgerRemoveOperationResult, LedgerRemoveRequest
from ...application.ledger.reset_operation import LedgerResetOperationResult, LedgerResetRequest
from ...application.ledger.review_operation import LedgerReviewProjection
from ...application.ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from ...application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ...application.ledger.update_contracts import LedgerUpdateOperationResult, LedgerUpdateRequest
from ...application.ledger.view_operation import LedgerViewProjection, LedgerViewRequest
from ...application.operations.capabilities import OperationRequestStoragePolicy
from ...application.review.filter import LedgerReviewStatus
from ...core.invoice_link import LinkInconsistencyDirection
from ...core.operations import (
    OperationEffect,
)
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ...domain.buckets.event import BucketEventType
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.service import LinkInconsistency
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.models import TransactionCatalogue
from ..adapter_composition_work_ports import build_ledger_evidence_ports
from .registered_executor_case_support import (
    _resolve_result_projection,
)
from .registered_executor_outcome_context import ExecutorOutcome
from .registered_executor_result_assertions import (
    _assert_canonical_bulk_classification_update,
    _assert_ledger_participation_lookup_result,
    _assert_ledger_participation_rebuild_result,
    _assert_ledger_review_projection,
    _assert_ledger_track_result,
)
from .registered_executor_scenario_constants import (
    _LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
    _OWN_ACCOUNT_SYNTHETIC_IBAN,
)


def assert_ledger_counterparty_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.counterparty public result and effects."""
    assert isinstance(ctx.payload, LedgerCounterpartyRequest)
    result = ctx.resolve(LedgerCounterpartyResult)
    assert isinstance(result, LedgerCounterpartyResult)
    assert result.profile_id == ctx.profile_id
    assert result.action == ctx.payload.action == "confirm"
    assert result.changed is True
    assert result.recorded is True
    assert result.facts is not None
    assert result.facts.territorial_scope == "es_canarias"
    assert result.facts.asserted_by == ctx.payload.asserted_by
    persisted = build_counterparty_establishment_repository(bucket_id=str(ctx.profile_id)).load(
        result.facts.counterparty_key
    )
    assert persisted is not None
    assert persisted.counterparty_key == result.facts.counterparty_key
    assert persisted.canonical_tax_identifier == result.facts.canonical_tax_identifier
    assert persisted.territorial_scope is not None
    assert persisted.territorial_scope.value == result.facts.territorial_scope
    assert persisted.asserted_by == ctx.payload.asserted_by


def assert_ledger_own_account_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.own_account public result and effects."""
    assert isinstance(ctx.payload, LedgerOwnAccountRequest)
    result = ctx.resolve(LedgerOwnAccountResult)
    assert isinstance(result, LedgerOwnAccountResult)
    assert result.profile_id == ctx.profile_id
    assert result.action == "add"
    assert result.changed is True
    assert result.own_account_id == "acc-01"
    assert [account.masked_iban for account in result.accounts] == ["ES \u00b7\u00b7\u00b7\u00b7 1332"]
    assert _OWN_ACCOUNT_SYNTHETIC_IBAN[4:-4] not in result.model_dump_json()
    persisted = OwnAccountRepository(bucket_id=str(ctx.profile_id)).load()
    assert [account.iban for account in persisted.accounts] == [_OWN_ACCOUNT_SYNTHETIC_IBAN]


def assert_ledger_remove_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.remove public result and effects."""
    assert isinstance(ctx.payload, LedgerRemoveRequest)
    removal = ctx.resolve(LedgerRemoveOperationResult)
    assert isinstance(removal, LedgerRemoveOperationResult)
    assert removal.profile_id == ctx.profile_id
    assert removal.report.transaction_id == ctx.payload.transaction_id
    assert removal.report.removed is False
    assert removal.report.dry_run is True
    assert any(
        transaction.transaction_id == ctx.payload.transaction_id
        for transaction in TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    )


def assert_ledger_allocate_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.allocate public result and effects."""
    assert isinstance(ctx.payload, LedgerAllocateRequest)
    allocated = ctx.resolve(LedgerAllocateOperationResult)
    assert isinstance(allocated, LedgerAllocateOperationResult)
    assert allocated.profile_id == ctx.profile_id
    assert allocated.transaction.transaction_id == ctx.payload.transaction_id
    assert allocated.transaction.business_classification == "MIXED"
    assert allocated.transaction.business_pct == "0.5"
    persisted_allocation = (
        TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load().get(ctx.payload.transaction_id)
    )
    assert persisted_allocation is not None
    assert persisted_allocation.business_classification is BusinessClassification.MIXED
    assert persisted_allocation.business_pct == Decimal("0.5")


def assert_ledger_classify_single_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.classify.single public result and effects."""
    assert isinstance(ctx.payload, LedgerClassifyRequest)
    classified = ctx.resolve(LedgerClassifyOperationResult)
    assert isinstance(classified, LedgerClassifyOperationResult)
    assert classified.profile_id == ctx.profile_id
    assert classified.outcome == "classified"
    assert classified.transaction is not None
    assert classified.transaction.transaction_id == ctx.payload.transaction_id
    assert classified.transaction.business_classification == "BUSINESS"
    assert classified.bucket_event_ids
    persisted_classification = (
        TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load().get(ctx.payload.transaction_id)
    )
    assert persisted_classification is not None
    assert persisted_classification.business_classification is BusinessClassification.BUSINESS


def assert_ledger_evidence_add_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.evidence.add public result and effects."""
    assert isinstance(ctx.payload, LedgerEvidenceAddRequest)
    added_evidence = ctx.resolve(LedgerEvidenceAddProjection)
    assert isinstance(added_evidence, LedgerEvidenceAddProjection)
    assert added_evidence.profile_id == ctx.profile_id
    assert added_evidence.record.bucket_id == str(ctx.profile_id)
    assert added_evidence.record.source_path == ctx.payload.source_path
    assert added_evidence.bucket_event_ids
    persisted_evidence = build_ledger_evidence_ports(bucket_id=str(ctx.profile_id)).evidence_repository.load(
        bucket_id=str(ctx.profile_id)
    )
    assert len(persisted_evidence) == 1
    assert persisted_evidence[0].evidence_id == added_evidence.record.evidence_id


def assert_ledger_evidence_list_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.evidence.list public result and effects."""
    assert isinstance(ctx.payload, LedgerEvidenceListRequest)
    listed = ctx.resolve(LedgerEvidenceListProjection)
    assert isinstance(listed, LedgerEvidenceListProjection)
    assert listed.profile_id == ctx.profile_id
    assert listed.count == len(listed.rows) == 1
    assert listed.rows[0].bucket_id == str(ctx.profile_id)


def assert_ledger_evidence_view_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.evidence.view public result and effects."""
    assert isinstance(ctx.payload, LedgerEvidenceViewRequest)
    viewed = ctx.resolve(LedgerEvidenceViewProjection)
    assert isinstance(viewed, LedgerEvidenceViewProjection)
    assert viewed.profile_id == ctx.profile_id
    assert isinstance(viewed.outcome, LedgerEvidenceViewSuccess)
    assert viewed.outcome.record.bucket_id == str(ctx.profile_id)
    assert viewed.outcome.record.evidence_id == ctx.payload.evidence_id


def assert_ledger_evidence_update_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.evidence.update public result and effects."""
    assert isinstance(ctx.payload, LedgerEvidenceUpdateRequest)
    updated_evidence = ctx.resolve(LedgerEvidenceUpdateProjection)
    assert isinstance(updated_evidence, LedgerEvidenceUpdateProjection)
    assert updated_evidence.profile_id == ctx.profile_id
    assert updated_evidence.record.evidence_id == ctx.payload.evidence_id
    assert updated_evidence.record.supplier == "Conformance Supplier"
    assert updated_evidence.bucket_event_ids
    persisted_evidence = build_ledger_evidence_ports(bucket_id=str(ctx.profile_id)).evidence_repository.load(
        bucket_id=str(ctx.profile_id)
    )
    assert len(persisted_evidence) == 1
    assert persisted_evidence[0].supplier == "Conformance Supplier"


def assert_ledger_evidence_remove_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.evidence.remove public result and effects."""
    assert isinstance(ctx.payload, LedgerEvidenceRemoveRequest)
    removed_evidence = ctx.resolve(LedgerEvidenceRemoveProjection)
    assert isinstance(removed_evidence, LedgerEvidenceRemoveProjection)
    assert removed_evidence.profile_id == ctx.profile_id
    assert removed_evidence.record.evidence_id == ctx.payload.evidence_id
    assert removed_evidence.bucket_event_ids
    persisted_evidence = build_ledger_evidence_ports(bucket_id=str(ctx.profile_id)).evidence_repository.load(
        bucket_id=str(ctx.profile_id)
    )
    assert persisted_evidence == ()


def assert_ledger_split_manual_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.split.manual public result and effects."""
    assert isinstance(ctx.payload, LedgerSplitRequest)
    split = ctx.resolve(LedgerSplitOperationResult)
    assert isinstance(split, LedgerSplitOperationResult)
    assert split.profile_id == ctx.profile_id
    assert split.parent_transaction_id == ctx.payload.transaction_id
    assert len(split.child_transaction_ids) == 2
    persisted_split = TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    assert all(child_id in persisted_split.transactions for child_id in split.child_transaction_ids)
    # The parent stays stored and split; the result names what recombines the cohort.
    split_parent = persisted_split.transactions[split.parent_transaction_id]
    assert split_parent.lifecycle_state.value == "SPLIT"
    assert split.parent_business_classification is split_parent.business_classification
    assert split.child_business_classification is BusinessClassification.NOT_YET_PROCESSED
    assert split.remerged_by == ("ledger.merge",)


def assert_ledger_merge_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.merge public result and effects."""
    assert isinstance(ctx.payload, LedgerMergeRequest)
    merged = ctx.resolve(LedgerMergeOperationResult)
    assert isinstance(merged, LedgerMergeOperationResult)
    assert merged.profile_id == ctx.profile_id
    assert merged.source_child_ids == tuple(sorted(ctx.payload.child_ids))
    persisted_merge = TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    assert merged.merged_transaction_id in persisted_merge.transactions
    assert all(child_id in persisted_merge.transactions for child_id in merged.source_child_ids)


def assert_ledger_update_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.update public result and effects."""
    assert isinstance(ctx.payload, LedgerUpdateRequest)
    updated = ctx.resolve(LedgerUpdateOperationResult)
    assert isinstance(updated, LedgerUpdateOperationResult)
    assert updated.profile_id == ctx.profile_id
    assert updated.outcome == "updated"
    assert updated.transaction is not None
    assert updated.transaction.description == "updated through registered operation"
    assert updated.bucket_event_ids
    persisted_update = (
        TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load().get(updated.transaction.transaction_id)
    )
    assert persisted_update is not None
    assert persisted_update.raw.description == "updated through registered operation"


def assert_ledger_reset_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.reset public result and effects."""
    assert isinstance(ctx.payload, LedgerResetRequest)
    reset = ctx.resolve(LedgerResetOperationResult)
    assert isinstance(reset, LedgerResetOperationResult)
    assert reset.profile_id == ctx.profile_id
    assert reset.report.reset is True
    assert reset.report.dry_run is False
    assert reset.report.reason == ctx.payload.reason
    assert len(reset.report.removed_transaction_ids) == 1
    assert reset.report.bucket_event_ids
    assert tuple(TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()) == ()


def assert_ledger_import_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.import public result and effects."""
    assert isinstance(ctx.payload, LedgerImportRequest)
    imported = ctx.resolve(LedgerImportResultProjection)
    assert isinstance(imported, LedgerImportResultProjection)
    assert imported.profile_id == ctx.profile_id
    assert imported.bucket_id == str(ctx.profile_id)
    assert imported.dry_run is True
    assert imported.rows == imported.imported == imported.skipped == imported.likely_duplicates == 0
    assert len(imported.refused_files) == 1
    assert imported.refused_files[0].file_name == "missing.csv"
    assert imported.refused_files[0].reason_code == "transaction_validation"
    assert tuple(TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()) == ()


def assert_ledger_add_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.add public result and effects."""
    assert isinstance(ctx.payload, LedgerAddRequest)
    added = ctx.resolve(LedgerAddOperationResult)
    assert isinstance(added, LedgerAddOperationResult)
    assert added.profile_id == ctx.profile_id
    assert added.outcome == "created"
    assert added.transaction is not None
    assert added.transaction.description == ctx.payload.description
    assert added.bucket_event_ids
    persisted_add = (
        TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load().get(added.transaction.transaction_id)
    )
    assert persisted_add is not None
    assert persisted_add.raw.description == ctx.payload.description


def assert_ledger_status_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.status public result and effects."""
    assert isinstance(ctx.payload, LedgerStatusRequest)
    status = ctx.resolve(LedgerStatusProjection)
    assert isinstance(status, LedgerStatusProjection)
    assert status.profile_id == ctx.profile_id
    assert status.period is None
    assert Decimal(status.business_income_total) == Decimal("0")
    assert Decimal(status.business_expense_total) == Decimal("0")
    assert Decimal(status.business_net_total) == Decimal("0")
    assert status.total_count == 0
    assert status.active_count == status.archived_count == status.stashed_count == 0
    assert status.readiness_issues == ()
    assert status.stale_filings == ()


def assert_ledger_check_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.check public result and effects."""
    assert isinstance(ctx.payload, LedgerCheckRequest)
    check = ctx.resolve(LedgerCheckProjection)
    assert isinstance(check, LedgerCheckProjection)
    assert ctx.payload.period is not None
    assert check.profile_id == ctx.profile_id
    assert check.period == ctx.payload.period
    assert check.periods == (str(ctx.payload.period.to_period()),)
    assert check.checked_transaction_count == 0
    assert check.issues == ()
    assert not check.ready
    invoices = InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load().invoices
    assert len(invoices) == 1
    invoice = next(iter(invoices.values()))
    assert check.link_inconsistencies == (
        LinkInconsistency(
            invoice_id=invoice.invoice_id,
            transaction_id="f" * 64,
            direction=LinkInconsistencyDirection.INVOICE_ONLY,
        ),
    )
    assert len(TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()) == 0
    assert ctx.definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


def assert_ledger_invoice_add_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.invoice.add public result and effects."""
    created = ctx.resolve(InvoiceAddResult)
    assert isinstance(created, InvoiceAddResult)
    assert created.profile_id == ctx.profile_id
    assert created.outcome == "created"
    catalogue = InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    assert len(catalogue.invoices) == 1
    assert created.invoice is not None
    invoice = catalogue.invoices[created.invoice.invoice_id]
    assert invoice.invoice_number == "CONFORMANCE-INVOICE-2025-ADD"
    assert invoice.grand_total == Decimal("121.00")
    assert created.invoice == CatalogueInvoiceSnapshot.from_invoice(invoice)


def assert_invoice_list_outcome(ctx: ExecutorOutcome) -> None:
    """Check the INVOICE_LIST_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, InvoiceListRequest)
    inventory = ctx.resolve(InvoiceListProjection)
    assert isinstance(inventory, InvoiceListProjection)
    assert inventory.profile_id == ctx.profile_id
    assert inventory.kind is None
    assert ctx.invoice_catalogue_before is not None
    assert tuple(inventory.invoices) == tuple(
        CatalogueInvoiceSnapshot.from_invoice(invoice) for invoice in ctx.invoice_catalogue_before.values()
    )
    assert len(inventory.invoices) == 1
    assert_invoice_catalogue_unchanged(ctx)


def assert_invoice_view_outcome(ctx: ExecutorOutcome) -> None:
    """Check the INVOICE_VIEW_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, InvoiceViewRequest)
    selection = ctx.resolve(InvoiceViewProjection)
    assert isinstance(selection, InvoiceViewProjection)
    assert selection.profile_id == ctx.profile_id
    assert selection.invoice_id == ctx.payload.invoice_id
    assert isinstance(selection.outcome, InvoiceViewSuccess)
    assert ctx.invoice_catalogue_before is not None
    assert selection.outcome.invoice == CatalogueInvoiceSnapshot.from_invoice(
        ctx.invoice_catalogue_before.invoices[ctx.payload.invoice_id]
    )
    assert_invoice_catalogue_unchanged(ctx)


def assert_invoice_remove_outcome(ctx: ExecutorOutcome) -> None:
    """Check the INVOICE_REMOVE_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, InvoiceRemoveRequest)
    removal = ctx.resolve(InvoiceRemoveResult)
    assert isinstance(removal, InvoiceRemoveResult)
    assert removal.profile_id == ctx.profile_id
    assert removal.invoice_id == ctx.payload.invoice_id
    assert ctx.invoice_catalogue_before is not None
    removed_invoice = ctx.invoice_catalogue_before.invoices[ctx.payload.invoice_id]
    assert removal.invoice == CatalogueInvoiceSnapshot.from_invoice(removed_invoice)
    expected_catalogue = InvoiceCatalogue(
        invoices={
            invoice_id: invoice
            for invoice_id, invoice in ctx.invoice_catalogue_before.invoices.items()
            if invoice_id != ctx.payload.invoice_id
        }
    )
    assert InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load() == expected_catalogue


def assert_invoice_update_outcome(ctx: ExecutorOutcome) -> None:
    """Check the INVOICE_UPDATE_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, InvoiceUpdateRequest)
    update = ctx.resolve(InvoiceUpdateResult)
    assert isinstance(update, InvoiceUpdateResult)
    assert update.profile_id == ctx.profile_id
    assert update.invoice_id == ctx.payload.invoice_id
    assert update.invoice.invoice_id == ctx.payload.invoice_id
    assert update.invoice.counterparty_name == "Updated conformance supplier"
    assert update.invoice.retention_amount is not None
    assert Decimal(update.invoice.retention_amount.decimal) == Decimal("0.00")
    assert update.bucket_event_ids
    assert ctx.invoice_catalogue_before is not None
    original = ctx.invoice_catalogue_before.invoices[ctx.payload.invoice_id]
    persisted = InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    assert set(persisted.invoices) == set(ctx.invoice_catalogue_before.invoices)
    corrected = persisted.invoices[ctx.payload.invoice_id]
    assert corrected.invoice_id == original.invoice_id
    assert corrected.counterparty_name == "Updated conformance supplier"
    assert corrected.retention_amount == Decimal("0.00")
    assert corrected.notes == original.notes
    assert corrected.linked_transaction_ids == original.linked_transaction_ids
    assert (
        corrected.model_copy(
            update={
                "counterparty_name": original.counterparty_name,
                "retention_amount": original.retention_amount,
                "updated_at": original.updated_at,
            }
        )
        == original
    )
    for invoice_id, invoice in ctx.invoice_catalogue_before.invoices.items():
        if invoice_id != ctx.payload.invoice_id:
            assert persisted.invoices[invoice_id] == invoice
    event_catalogue = BucketEventHistoryRepository().load()
    assert all(event_id in event_catalogue.events for event_id in update.bucket_event_ids)
    assert any(
        event_catalogue.events[event_id].object_id == ctx.payload.invoice_id
        and event_catalogue.events[event_id].event_type is BucketEventType.PAYABLE_INVOICE_UPDATED
        for event_id in update.bucket_event_ids
    )


def assert_invoice_catalogue_unchanged(ctx: ExecutorOutcome) -> None:
    """Check the invoice catalogue is unchanged by a read."""
    assert ctx.invoice_catalogue_before is not None
    assert InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).load() == ctx.invoice_catalogue_before


def assert_ledger_preflight_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.preflight public result and effects."""
    assert isinstance(ctx.payload, LedgerPreflightRequest)
    preflight = ctx.resolve(LedgerPreflightProjection)
    assert isinstance(preflight, LedgerPreflightProjection)
    assert preflight.profile_id == ctx.profile_id
    assert preflight.period == ctx.payload.period
    assert preflight.checked_transaction_count == 1
    assert not preflight.ready
    transactions = TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    assert len(transactions) == 2
    transaction_ids_by_description = {
        transaction.raw.description: transaction.transaction_id for transaction in transactions.values()
    }
    selected_transaction_id = transaction_ids_by_description["conformance preflight selected-period issue"]
    outside_transaction_id = transaction_ids_by_description["conformance preflight outside-period issue"]
    assert len(preflight.issues) == 1
    assert preflight.issues[0].transaction_id == selected_transaction_id
    assert preflight.issues[0].reason is LedgerPreflightIssueReason.MISSING_CATEGORY
    assert outside_transaction_id not in {issue.transaction_id for issue in preflight.issues}
    assert ctx.definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


def assert_ledger_list_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.list public result and effects."""
    assert isinstance(ctx.payload, LedgerListRequest)
    selection = ctx.resolve(LedgerListProjection)
    assert isinstance(selection, LedgerListProjection)
    assert selection.profile_id == ctx.profile_id
    assert selection.total == 3
    assert selection.truncated is True
    assert selection.offset == ctx.payload.offset == 1
    assert selection.limit == ctx.payload.limit == 2
    assert selection.by_group is False
    assert [row.transaction.description for row in selection.rows] == [
        "ledger list page B",
        "ledger list page C",
    ]
    assert all(row.group_label == _LEDGER_LIST_PRIVATE_FILTER_SENTINEL for row in selection.rows)
    materialization = asyncio.run(
        ctx.driver.services.observation.reader.read_observation(
            ctx.submitted.receipt.operation_id,
            0,
            limit=256,
        )
    )
    assert materialization.snapshot.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert materialization.snapshot.credential_free_request_json is None
    journal_file = (
        ctx.tmp_path
        / ctx.case.definition_id
        / "cadrumo-storage"
        / "operations"
        / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path()
        / f"{ctx.submitted.receipt.operation_id}.json"
    )
    assert journal_file.is_file()
    assert _LEDGER_LIST_PRIVATE_FILTER_SENTINEL.encode() not in journal_file.read_bytes()


def assert_ledger_history_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.history public result and effects."""
    assert isinstance(ctx.payload, LedgerHistoryRequest)
    history = ctx.resolve(LedgerHistoryProjection)
    assert isinstance(history, LedgerHistoryProjection)
    assert history.profile_id == ctx.profile_id
    assert history.transaction_prefix == ctx.payload.transaction_prefix
    assert history.include_split_siblings is False
    assert history.event_count == 1
    assert len(history.events) == 1
    assert history.transaction_id in history.object_ids


def assert_ledger_view_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.view public result and effects."""
    assert isinstance(ctx.payload, LedgerViewRequest)
    view = ctx.resolve(LedgerViewProjection)
    assert isinstance(view, LedgerViewProjection)
    assert view.profile_id == ctx.profile_id
    assert view.transaction_prefix == ctx.payload.transaction_prefix
    assert view.transaction.transaction_id.startswith(ctx.payload.transaction_prefix)
    assert view.transaction.description == "conformance view seed"
    assert view.review_status is LedgerReviewStatus.PENDING
    assert view.latest_llm_rejection is not None
    assert view.latest_llm_rejection.operator_reason == "operator rejected the conformance suggestion"


def assert_ledger_track_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.track public result and effects."""
    _assert_ledger_track_result(
        ctx.driver,
        ctx.registry,
        profile_id=ctx.profile_id,
        operation=ctx.operation,
        payload=ctx.payload,
        operation_id=ctx.submitted.receipt.operation_id,
        terminal_revision=ctx.observed.projection.revision,
    )


def assert_ledger_participation_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.participation public result and effects."""
    assert isinstance(ctx.payload, LedgerParticipationRequest)
    _assert_ledger_participation_lookup_result(
        ctx.driver,
        ctx.registry,
        profile_id=ctx.profile_id,
        payload=ctx.payload,
        operation_id=ctx.submitted.receipt.operation_id,
        terminal_revision=ctx.observed.projection.revision,
    )


def assert_ledger_participation_rebuild_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.participation.rebuild public result and effects."""
    assert isinstance(ctx.payload, LedgerParticipationRebuildRequest)
    _assert_ledger_participation_rebuild_result(
        ctx.driver,
        ctx.registry,
        profile_id=ctx.profile_id,
        operation=ctx.operation,
        operation_id=ctx.submitted.receipt.operation_id,
        terminal_revision=ctx.observed.projection.revision,
    )


def assert_ledger_review_outcome(ctx: ExecutorOutcome) -> None:
    """Check the ledger.review public result and effects."""
    review = _resolve_result_projection(
        ctx.driver,
        ctx.registry,
        definition_id=ctx.definition_id,
        operation_id=ctx.submitted.receipt.operation_id,
        terminal_revision=ctx.observed.projection.revision,
        projection_type=LedgerReviewProjection,
    )
    _assert_ledger_review_projection(ctx.payload, review, profile_id=ctx.profile_id)


def assert_ledger_bulk_classify_outcome(ctx: ExecutorOutcome) -> None:
    """Check the LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID public result and effects."""
    assert isinstance(ctx.payload, LedgerBulkClassifyRequest)
    bulk_projection = ctx.resolve(LedgerBulkClassifyProjection)
    assert isinstance(bulk_projection, LedgerBulkClassifyProjection)
    assert bulk_projection.profile_id == ctx.profile_id
    assert bulk_projection.outcome == "classified"
    assert bulk_projection.result is not None
    result = bulk_projection.result
    assert result.total == 2
    assert result.applied == 1
    assert result.skipped == 0
    assert len(result.failures) == 1

    csv_rows = tuple(csv.DictReader(ctx.payload.csv_text.splitlines()))
    assert len(csv_rows) == 2
    valid_row, invalid_row = csv_rows
    valid_transaction_id = valid_row["transaction_id"]
    invalid_transaction_id = invalid_row["transaction_id"]
    assert valid_transaction_id is not None
    assert invalid_transaction_id is not None
    assert valid_row["iva_category"] == "domestic_general"
    assert invalid_row["iva_category"] == "not-a-declared-category"
    assert result.failures[0].row_index == 1
    assert result.failures[0].transaction_id == invalid_transaction_id
    assert "not declared by the facts registry" in result.failures[0].reason

    assert ctx.bulk_classify_before is not None
    transactions_before, history_before = ctx.bulk_classify_before
    transactions_after = TransactionCatalogueRepository(bucket_id=str(ctx.profile_id)).load()
    history_after = bucket_event_history_repository(bucket_id=str(ctx.profile_id)).load()
    assert transactions_after.transactions.keys() == transactions_before.transactions.keys()
    assert transactions_after.get(invalid_transaction_id) == transactions_before.get(invalid_transaction_id)
    assert all(history_after.events.get(event_id) == event for event_id, event in history_before.events.items())
    new_events = tuple(
        event for event_id, event in history_after.events.items() if event_id not in history_before.events
    )
    assert len(new_events) == 1
    event = new_events[0]
    assert result.bucket_event_ids == (event.event_id,)

    before_transaction = transactions_before.get(valid_transaction_id)
    after_transaction = transactions_after.get(valid_transaction_id)
    assert before_transaction is not None
    assert after_transaction is not None
    _assert_canonical_bulk_classification_update(
        profile_id=ctx.profile_id,
        operation=ctx.operation,
        before=before_transaction,
        after=after_transaction,
        patch=ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.BUSINESS,
            iva_category=IvaCategory("domestic_general"),
        ),
        actor=ctx.payload.actor or str(ctx.profile_id),
        event=event,
    )

    expected_transactions = dict(transactions_before.transactions)
    expected_transactions[valid_transaction_id] = after_transaction
    assert transactions_after == TransactionCatalogue.from_transactions(expected_transactions.values())


LEDGER_OUTCOME_ASSERTIONS: dict[str, Callable[[ExecutorOutcome], None]] = {
    "ledger.counterparty": assert_ledger_counterparty_outcome,
    "ledger.own_account": assert_ledger_own_account_outcome,
    "ledger.remove": assert_ledger_remove_outcome,
    "ledger.allocate": assert_ledger_allocate_outcome,
    "ledger.classify.single": assert_ledger_classify_single_outcome,
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID: assert_ledger_bulk_classify_outcome,
    "ledger.evidence.add": assert_ledger_evidence_add_outcome,
    "ledger.evidence.list": assert_ledger_evidence_list_outcome,
    "ledger.evidence.view": assert_ledger_evidence_view_outcome,
    "ledger.evidence.update": assert_ledger_evidence_update_outcome,
    "ledger.evidence.remove": assert_ledger_evidence_remove_outcome,
    "ledger.split.manual": assert_ledger_split_manual_outcome,
    "ledger.merge": assert_ledger_merge_outcome,
    "ledger.update": assert_ledger_update_outcome,
    "ledger.reset": assert_ledger_reset_outcome,
    "ledger.import": assert_ledger_import_outcome,
    "ledger.add": assert_ledger_add_outcome,
    "ledger.status": assert_ledger_status_outcome,
    "ledger.check": assert_ledger_check_outcome,
    "ledger.invoice.add": assert_ledger_invoice_add_outcome,
    INVOICE_LIST_OPERATION_DEFINITION_ID: assert_invoice_list_outcome,
    INVOICE_VIEW_OPERATION_DEFINITION_ID: assert_invoice_view_outcome,
    INVOICE_REMOVE_OPERATION_DEFINITION_ID: assert_invoice_remove_outcome,
    INVOICE_UPDATE_OPERATION_DEFINITION_ID: assert_invoice_update_outcome,
    "ledger.preflight": assert_ledger_preflight_outcome,
    "ledger.list": assert_ledger_list_outcome,
    "ledger.history": assert_ledger_history_outcome,
    "ledger.view": assert_ledger_view_outcome,
    "ledger.track": assert_ledger_track_outcome,
    "ledger.participation": assert_ledger_participation_outcome,
    "ledger.participation.rebuild": assert_ledger_participation_rebuild_outcome,
    "ledger.review": assert_ledger_review_outcome,
}
