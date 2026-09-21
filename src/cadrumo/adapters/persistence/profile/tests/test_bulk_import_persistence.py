"""Encrypted-catalogue integration checks for bulk invoice import."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from cadrumo.domain.iva.classification import InvoiceKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "29292929-2929-4292-8292-292929292929"
_CIF = "A58818501"


def _csv_source(text: str, tmp_path: Path):
    csv_path = tmp_path / "bulk.csv"
    csv_path.write_text(text, encoding="utf-8")
    return read_bulk_invoice_import_source(csv_path)


def test_import_invoices_from_rows_persists_through_create_catalogue_invoice(tmp_path: Path) -> None:
    """Each valid row creates a real, reloadable catalogue invoice."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
        rows = _csv_source(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-A-001,2026-05-01,100.00,21\n"
            f"{_CIF},Papeleria Sol SL,BULK-A-002,2026-05-02,50.00,10\n",
            tmp_path,
        )
        result = import_invoices_from_rows(
            rows,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=ports,
        )

        assert result.rows == 2
        assert result.created == 2
        assert result.skipped_duplicate == 0
        assert result.refused == ()
        assert len(result.created_invoice_ids) == 2

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        stored_numbers = {invoice.invoice_number for invoice in catalogue.invoices.values()}
        assert stored_numbers == {"BULK-A-001", "BULK-A-002"}
        for invoice_id in result.created_invoice_ids:
            assert invoice_id in catalogue.invoices


def test_bulk_import_provenance_survives_encrypted_catalogue_reopen(tmp_path: Path) -> None:
    """One accepted row keeps its exact sanitized source association after reopen."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
        source = _csv_source(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-PROV-REOPEN,2026-05-01,100.00,21\n",
            tmp_path,
        )
        expected_provenance = source.rows[0].provenance
        assert expected_provenance is not None
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=ports,
        )

        assert result.created == 1
        assert len(result.created_invoice_ids) == 1
        reopened = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        invoice = reopened.invoices[result.created_invoice_ids[0]]

        assert invoice.provenance == expected_provenance
        assert invoice.provenance is not None
        assert invoice.provenance.source_path == Path("bulk.csv")
        assert str(tmp_path) not in invoice.provenance.model_dump_json()
        assert "raw_fields" not in invoice.provenance.model_dump_json()


def test_import_invoices_from_rows_reimport_is_idempotent_no_op(tmp_path: Path) -> None:
    """Re-running the identical rows a second time skips every row as a duplicate."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
        rows = _csv_source(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-B-001,2026-05-01,100.00,21\n",
            tmp_path,
        )
        first = import_invoices_from_rows(
            rows,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=ports,
        )
        assert first.created == 1

        second = import_invoices_from_rows(
            rows,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            declared_country="ES",
            ports=ports,
        )
        assert second.created == 0
        assert second.skipped_duplicate == 1
        assert second.refused == ()

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        matching = [inv for inv in catalogue.invoices.values() if inv.invoice_number == "BULK-B-001"]
        assert len(matching) == 1


def test_a_declared_country_never_overrides_a_row_that_states_one(tmp_path: Path) -> None:
    """A whole-import country fills a blank row but never overrides a stated one."""
    source_text = (
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,country_code\n"
        f"{_CIF},Papeleria Sol SL,BULK-CTY-010,2026-05-01,100.00,21,ES\n"
        "DE811907980,Papier Nord GmbH,BULK-CTY-011,2026-05-02,200.00,21,\n"
    )
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        ports = build_catalogue_creation_ports(bucket_id=_BUCKET_ID)
        source = _csv_source(source_text, tmp_path)
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            declared_country="DE",
            ports=ports,
        )

        assert result.created == 2
        assert result.refused == ()

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        by_number = {inv.invoice_number: inv.counterparty_country for inv in catalogue.invoices.values()}
        assert by_number["BULK-CTY-010"] == "ES"
        assert by_number["BULK-CTY-011"] == "DE"
