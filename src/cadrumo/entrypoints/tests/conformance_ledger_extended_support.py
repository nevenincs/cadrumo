"""Real ledger intake, export, derivation and unavailable-reader settlement cases."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from ...adapters.outbound.llm.models import UsageRecord
from ...adapters.persistence.llm.usage import UsageRecorder
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...application.invoices.catalogue_intake_contracts import (
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceWizardOutcome,
    InvoiceWizardRequest,
)
from ...application.ledger.actions_manual import create_manual_transaction
from ...application.ledger.evidence_ingestion_contracts import (
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
    LedgerEvidencePullAllRequest,
    LedgerEvidencePullRequest,
)
from ...application.ledger.export_operation import LedgerExportProjection, LedgerExportRequest
from ...application.ledger.link_operation import LedgerLinkOperationResult, LedgerLinkRequest
from ...application.ledger.llm_diagnostics_operation import LedgerLlmDiagnosticsProjection, LedgerLlmDiagnosticsRequest
from ...application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from ...core.config_support import LLMProvider
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import DocumentLinkSource
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ...domain.iva.classification import InvoiceKind
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ..ledger_action_composition import compose_ledger_action_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    definition_id = context.definition.definition_id
    transactions = TransactionCatalogueRepository(bucket_id=profile)
    invoices = InvoiceCatalogueRepository(bucket_id=profile)
    request: BaseModel
    if definition_id in {
        "ledger.classify.iva-derive",
        "ledger.classify.review",
        "ledger.split.review",
        "ledger.evidence.pull",
        "ledger.export",
        "ledger.link",
    }:
        seeded = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=profile,
                booked_date=date(2025, 4, 15),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="conformance ledger expense",
                business_classification=BusinessClassification.BUSINESS,
                actor="conformance",
            ),
            ports=compose_ledger_action_ports(bucket_id=profile, operation=context.operation),
        )
        transaction_id = seeded.ref.transaction_id
        before = transactions.load()
        if definition_id == "ledger.classify.iva-derive":
            request = LedgerOperatorIvaRequest(
                profile_id=context.profile_id,
                transaction_id=transaction_id[:16],
                iva_category="domestic_general",
                actor="conformance",
            )
        elif definition_id == "ledger.classify.review":
            request = LedgerLlmReviewRequest(
                profile_id=context.profile_id,
                transaction_id=transaction_id,
                mode="classification",
                origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
                preview=True,
            )
        elif definition_id == "ledger.split.review":
            request = LedgerLlmReviewRequest(
                profile_id=context.profile_id,
                transaction_id=transaction_id,
                mode="split",
                origin=LlmReviewInvocationOrigin.SPLIT_LLM,
                preview=True,
                read_evidence=False,
            )
        elif definition_id == "ledger.evidence.pull":
            request = LedgerEvidencePullRequest(
                profile_id=context.profile_id,
                transaction_id=transaction_id,
                source=DocumentLinkSource.GOOGLE_DRIVE,
                reference="https://drive.google.com/file/d/ABC123ticket/view",
            )
        elif definition_id == "ledger.export":
            request = LedgerExportRequest(
                profile_id=context.profile_id, output_path=str(context.input_root / "ledger.csv"), actor="conformance"
            )
        else:
            invoice = Invoice.model_validate(
                dict(
                    payment_status=PaymentStatus.PENDING,
                    kind=InvoiceKind.RECEIVED,
                    bucket_id=profile,
                    invoice_number="CONFORMANCE-LINK",
                    issued_at=date(2025, 4, 15),
                    counterparty_name="Conformance Supplier",
                    counterparty_tax_id="A58818501",
                    counterparty_country="ES",
                    base_total=Decimal("100.00"),
                    iva_total=Decimal("21.00"),
                    grand_total=Decimal("121.00"),
                    currency="EUR",
                    lines=(
                        InvoiceLine(
                            description="conformance expense",
                            quantity=Decimal("1"),
                            unit_price=Decimal("100"),
                            subtotal=Decimal("100"),
                            iva_rate=IvaRate.from_registry("RATE_21"),
                            iva_amount=Decimal("21"),
                        ),
                    ),
                )
            )
            invoices.save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))
            request = LedgerLinkRequest(
                profile_id=context.profile_id,
                transaction_id=transaction_id,
                invoice_id=invoice.invoice_id,
                actor="conformance",
            )

        def verify(outcome: ConformanceOutcome) -> None:
            if definition_id in {"ledger.classify.review", "ledger.split.review", "ledger.evidence.pull"}:
                assert transactions.load() == before
                if definition_id == "ledger.split.review":
                    assert outcome.observed.projection.failure_error_code == "ERROR_TRANSACTION_VALIDATION"
                return
            actual_row = transactions.load().get(transaction_id)
            assert actual_row is not None
            if definition_id == "ledger.classify.iva-derive":
                result = outcome.resolve_result(LedgerOperatorIvaResult)
                assert result.outcome == "derived" and result.derivable and result.transaction_id == transaction_id
                assert Decimal(result.iva_rate or "-1") == Decimal("0.21")
                assert Decimal(result.taxable_base or "-1") == Decimal("100")
                assert Decimal(result.iva_amount or "-1") == Decimal("21")
                assert actual_row.taxable_base == Decimal("100") and actual_row.iva_amount == Decimal("21")
                assert actual_row.raw.model_dump(exclude={"provenance", "raw_fields"}) == (
                    seeded.transaction.raw.model_dump(exclude={"provenance", "raw_fields"})
                )
                assert actual_row.business_classification is BusinessClassification.BUSINESS
                assert actual_row.raw.provenance.source_format == seeded.transaction.raw.provenance.source_format
                assert Decimal(actual_row.raw.raw_fields["taxable_base"]) == Decimal("100")
                assert Decimal(actual_row.raw.raw_fields["iva_rate"]) == Decimal("0.21")
                assert Decimal(actual_row.raw.raw_fields["iva_amount"]) == Decimal("21")
            elif definition_id == "ledger.link":
                result = outcome.resolve_result(LedgerLinkOperationResult)
                assert result.outcome == "linked" and result.projection is not None
                assert actual_row.invoice_id == result.invoice_id == invoice.invoice_id
                persisted_invoice = invoices.load().invoices[invoice.invoice_id]
                assert transaction_id in persisted_invoice.linked_transaction_ids
            else:
                result = outcome.resolve_result(LedgerExportProjection)
                output = Path(result.output_path)
                payload = output.read_bytes()
                assert (
                    result.row_count == 1 and result.byte_size == len(payload) and result.sha256 == sha256_hex(payload)
                )
                with output.open(encoding="utf-8", newline="") as handle:
                    rows = tuple(csv.DictReader(handle))
                assert len(rows) == 1 and rows[0]["transaction_id"] == transaction_id
                assert rows[0]["description"] == "conformance ledger expense"
                assert Decimal(rows[0]["amount"]) == Decimal("121.00")
                assert transactions.load() == before

        return ConformancePreparation(profile_operation_subject(profile), request, verify=verify)
    if definition_id == "ledger.evidence.batch":
        name = "facturae_32_series_and_parties_invoice.xml"
        corpus = Path(__file__).parents[2] / "application" / "ledger" / "tests" / "_evidence_corpus" / name
        payload = corpus.read_bytes()
        source = context.input_root / name
        source.write_bytes(payload)

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(LedgerEvidenceBatchProjection)
            assert result.profile_id == context.profile_id and result.write_count > 0
            assert not result.run.unresolved and len(result.run.items) == 1
            row = result.run.items[0]
            assert row.content_address == sha256_hex(payload) and row.source_name == name
            assert row.status in {"ingested", "pending_review"} and row.refusal_code is None
            store = AttachmentStore(bucket_id=profile)
            assert store.read_bytes(row.content_address) == payload
            assert store.load_manifest(row.content_address).bucket_id == profile

        return ConformancePreparation(
            profile_operation_subject(profile),
            LedgerEvidenceBatchRequest(
                profile_id=context.profile_id,
                sources=(str(source),),
                source_directory=str(context.input_root),
                direction=InvoiceKind.RECEIVED,
            ),
            verify=verify,
        )
    if definition_id == "ledger.evidence.pull_all":
        before = transactions.load()

        def verify(outcome: ConformanceOutcome) -> None:
            assert transactions.load() == before

        return ConformancePreparation(
            profile_operation_subject(profile),
            LedgerEvidencePullAllRequest(
                profile_id=context.profile_id,
                folder="https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz012345",
            ),
            verify=verify,
        )
    if definition_id == "ledger.invoice.import":
        source = context.input_root / "invoices.csv"
        source.write_text(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\nA58818501,Conformance Supplier,IMPORT-001,2025-04-15,100.00,21\nA58818501,Conformance Supplier,IMPORT-002,not-a-date,50.00,21\n",
            encoding="utf-8",
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InvoiceImportProjection)
            assert result.rows == 2 and result.created == 1 and result.skipped_duplicate == 0
            assert (
                len(result.refused) == 1
                and result.refused[0].row_number == 3
                and result.refused[0].field == "invoice_date"
            )
            stored = invoices.load().invoices
            assert len(stored) == 1 and result.created_invoice_ids == tuple(stored)
            invoice = next(iter(stored.values()))
            assert invoice.invoice_number == "IMPORT-001" and invoice.grand_total == Decimal("121.00")

        return ConformancePreparation(
            profile_operation_subject(profile),
            InvoiceImportRequest(
                profile_id=context.profile_id,
                kind=InvoiceKind.RECEIVED,
                source_path=str(source),
                source_sha256=sha256_hex(source.read_bytes()),
                country="ES",
            ),
            verify=verify,
        )
    if definition_id == "ledger.invoice.wizard":
        request = InvoiceWizardRequest(
            profile_id=context.profile_id,
            kind=InvoiceKind.RECEIVED,
            counterparty_nif="A58818501",
            counterparty_name="Conformance Supplier",
            invoice_number="WIZARD-001",
            invoice_date="2025-04-15",
            taxable_base="100.00",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
            notes="conformance wizard",
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InvoiceWizardOutcome)
            assert result.outcome == "succeeded" and result.result is not None
            assert not result.result.already_existed and not result.result.euro_value_pending
            stored = invoices.load().invoices
            assert len(stored) == 1
            invoice = next(iter(stored.values()))
            assert invoice.invoice_number == "WIZARD-001" and invoice.grand_total == Decimal("121.00")
            assert invoice.notes == "conformance wizard"

        return ConformancePreparation(profile_operation_subject(profile), request, verify=verify)
    if definition_id == "ledger.llm-diagnostics":
        UsageRecorder().record(
            UsageRecord(
                prompt_id="conformance",
                caller="conformance",
                text="synthetic",
                provider=LLMProvider.LOCAL,
                model="conformance",
                input_tokens=3,
                output_tokens=7,
                cost_estimate_usd=None,
                cache_hit=False,
                created_at=datetime(2026, 4, 1, tzinfo=UTC),
                request_id="a" * 64,
            )
        )

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(LedgerLlmDiagnosticsProjection)
            assert result.profile_id == context.profile_id and result.report.total_calls == 1
            assert result.report.total_input_tokens == 3 and result.report.total_output_tokens == 7
            assert result.report.total_unpriced_calls == 1 and result.report.total_cache_hits == 0
            assert len(result.report.usage_providers) == 1 and result.report.total_classified == 0

        return ConformancePreparation(
            profile_operation_subject(profile),
            LedgerLlmDiagnosticsRequest(profile_id=context.profile_id, since=date(2026, 4, 1), until=date(2026, 4, 1)),
            verify=verify,
        )
    raise AssertionError(definition_id)


LEDGER_EXTENDED_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            "ledger.classify.iva-derive",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.classify.iva-derive",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.classify.review",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("ledger.llm.acquire",),
            "REFUSED_LEDGER_EVIDENCE_READER",
        ),
        RegisteredExecutorConformanceCase(
            "ledger.split.review", OperationTerminalCondition.FAILED, OperationEffect.NONE, ("ledger.llm.acquire",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.batch",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.evidence.batch",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.pull",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("ledger.evidence.pull",),
            "REFUSED_OUTBOUND_STORAGE_VALIDATION",
        ),
        RegisteredExecutorConformanceCase(
            "ledger.evidence.pull_all",
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            ("ledger.evidence.pull_all",),
            "REFUSED_OUTBOUND_STORAGE_VALIDATION",
        ),
        RegisteredExecutorConformanceCase(
            "ledger.export", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.export",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.invoice.import",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.PARTIAL,
            ("ledger.invoice.import",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.invoice.wizard",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            ("ledger.invoice.wizard",),
        ),
        RegisteredExecutorConformanceCase(
            "ledger.link", OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED, ("ledger.link",)
        ),
        RegisteredExecutorConformanceCase(
            "ledger.llm-diagnostics",
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            ("ledger.llm-diagnostics",),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
