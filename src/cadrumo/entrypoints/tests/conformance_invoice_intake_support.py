"""Registered-executor conformance scenarios for invoice-book import and the invoice wizard."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID,
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceImportRowFailure,
    InvoiceWizardOutcome,
    InvoiceWizardRequest,
)
from ...application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.classification import InvoiceKind
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_COUNTERPARTY_NIF = "B12345674"
_COUNTERPARTY_NAME = "Conformance Supplier"
_BOOK_HEADER = (
    "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,currency,country_code"
)


def _book_row(invoice_number: str, invoice_date: str, taxable_base: str) -> str:
    return f"{_COUNTERPARTY_NIF},{_COUNTERPARTY_NAME},{invoice_number},{invoice_date},{taxable_base},21,EUR,ES"


def _prepare_import(context: ConformanceFamilyContext) -> ConformancePreparation:
    # Every column is written under the importer's own field name, so the
    # semantic column-mapping lane is never consulted. The book holds two new
    # invoices, an exact repeat of the first, and a row with no invoice number.
    book = context.input_root / "invoice-book.csv"
    book.write_text(
        "\n".join(
            (
                _BOOK_HEADER,
                _book_row("IMP-2025-001", "2025-02-03", "100.00"),
                _book_row("IMP-2025-002", "2025-02-10", "200.00"),
                _book_row("IMP-2025-001", "2025-02-03", "100.00"),
                _book_row("", "2025-02-17", "50.00"),
            )
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bucket_id = str(context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(InvoiceImportProjection)
        persisted = InvoiceCatalogueRepository(bucket_id=bucket_id).load().invoices
        # Every row is accounted for once: created, skipped as an exact repeat of an
        # already-catalogued identity, or refused with its physical line number and field.
        # bulk_import.py `import_invoices_from_rows`.
        assert projection.profile_id == context.profile_id
        assert (projection.rows, projection.created, projection.skipped_duplicate) == (4, 2, 1)
        assert projection.refused == (
            InvoiceImportRowFailure(row_number=5, field="invoice_number", reason="required field is missing or blank"),
        )
        assert projection.unmapped_column_headers == ()
        assert projection.mapping_reasons == ()
        assert set(projection.created_invoice_ids) == set(persisted)

        by_number = {invoice.invoice_number: invoice for invoice in persisted.values()}
        assert set(by_number) == {"IMP-2025-001", "IMP-2025-002"}
        for number, issued, base, iva in (
            ("IMP-2025-001", date(2025, 2, 3), Decimal("100.00"), Decimal("21.00")),
            ("IMP-2025-002", date(2025, 2, 10), Decimal("200.00"), Decimal("42.00")),
        ):
            invoice = by_number[number]
            assert invoice.kind is InvoiceKind.RECEIVED
            assert invoice.bucket_id == bucket_id
            assert invoice.counterparty_tax_id == _COUNTERPARTY_NIF
            assert invoice.issued_at == issued
            assert (invoice.base_total, invoice.iva_total, invoice.grand_total) == (base, iva, base + iva)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=InvoiceImportRequest(
            profile_id=context.profile_id,
            kind=InvoiceKind.RECEIVED,
            source_path=str(book),
            source_sha256=hashlib.sha256(book.read_bytes()).hexdigest(),
        ),
        verify=verify,
    )


def _prepare_wizard(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        wizard = outcome.resolve_result(InvoiceWizardOutcome)
        assert wizard.profile_id == context.profile_id
        assert wizard.outcome == "succeeded"
        assert wizard.refusal is None
        assert wizard.result is not None
        assert wizard.result.already_existed is False
        assert wizard.result.euro_value_pending is False

        (invoice,) = InvoiceCatalogueRepository(bucket_id=bucket_id).load().invoices.values()
        assert invoice.kind is InvoiceKind.RECEIVED
        assert invoice.invoice_number == "WIZ-2025-001"
        assert invoice.counterparty_tax_id == _COUNTERPARTY_NIF
        assert invoice.issued_at == date(2025, 3, 4)
        # 250.00 at the 21% rate: 52.50 of IVA on a 302.50 total.
        assert (invoice.base_total, invoice.iva_total, invoice.grand_total) == (
            Decimal("250.00"),
            Decimal("52.50"),
            Decimal("302.50"),
        )
        assert wizard.result.invoice == CatalogueInvoiceSnapshot.from_invoice(invoice)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=InvoiceWizardRequest(
            profile_id=context.profile_id,
            kind=InvoiceKind.RECEIVED,
            counterparty_nif=_COUNTERPARTY_NIF,
            counterparty_name=_COUNTERPARTY_NAME,
            invoice_number="WIZ-2025-001",
            invoice_date="2025-03-04",
            taxable_base="250.00",
            iva_rate="21",
            currency="EUR",
            country_code="ES",
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == INVOICE_IMPORT_OPERATION_DEFINITION_ID:
        return _prepare_import(context)
    if definition_id == INVOICE_WIZARD_OPERATION_DEFINITION_ID:
        return _prepare_wizard(context)
    raise AssertionError(f"no invoice intake conformance scenario for {definition_id}")


INVOICE_INTAKE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # Two rows commit and one is refused, so the import is a partial success.
        # catalogue_intake_executor.py `_invoice_intake_success_effect`.
        RegisteredExecutorConformanceCase(
            INVOICE_IMPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.PARTIAL,
            (INVOICE_IMPORT_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_WIZARD_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
