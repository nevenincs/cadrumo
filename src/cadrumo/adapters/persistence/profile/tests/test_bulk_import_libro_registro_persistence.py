"""Encrypted-catalogue integration checks for Spanish libro-registro import."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from cadrumo.core.field_role import FieldRole
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.tests.inventory import FIXTURES_DIR

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
_BUCKET_ID = "31313131-3131-4131-8131-313131313131"

_LIBRO_ROLES = (
    FieldRole.INVOICE_DATE,
    FieldRole.INVOICE_NUMBER,
    FieldRole.COUNTERPARTY_NAME,
    FieldRole.COUNTERPARTY_NIF,
    FieldRole.TAXABLE_BASE,
    FieldRole.IVA_RATE,
    FieldRole.IVA_AMOUNT,
    FieldRole.UNMAPPED,
    FieldRole.RETENCION_AMOUNT,
    FieldRole.GRAND_TOTAL,
)

_ROWS_REFUSED_BY_DOMAIN_RULES: dict[int, str] = {
    5: "totals must be non-negative",
    6: "must be exactly 9 characters",
    7: "must be exactly 9 characters",
    9: "required field is missing or blank",
}


def _mapper(headers):
    return _LIBRO_ROLES if len(headers) == len(_LIBRO_ROLES) else None


def test_the_libro_registro_imports_with_no_column_resolution_failure(tmp_path: Path) -> None:
    """Every row reaches the real encrypted catalogue under Spanish column names."""
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)
    assert len(source.rows) == 8

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            declared_country="ES",
            ports=build_catalogue_creation_ports(bucket_id=_BUCKET_ID),
        )

    assert result.rows == 8
    assert result.created == 4
    assert {failure.row_number for failure in result.refused} == set(_ROWS_REFUSED_BY_DOMAIN_RULES)
    for failure in result.refused:
        assert _ROWS_REFUSED_BY_DOMAIN_RULES[failure.row_number] in failure.reason, failure
        assert "column" not in failure.reason.casefold(), failure


def test_the_retencion_amount_reaches_the_catalogue_invoice(tmp_path: Path) -> None:
    """Retención is persisted on the catalogue invoice rather than dropped."""
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            declared_country="ES",
            ports=build_catalogue_creation_ports(bucket_id=_BUCKET_ID),
        )
        assert result.created == 4
        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()

    by_number = {invoice.invoice_number: invoice for invoice in catalogue.invoices.values()}
    first = by_number["2025/0142"]
    assert first.base_total == Decimal("4272.00")
    assert first.retention_amount == Decimal("640.80")

    withheld = [inv for inv in catalogue.invoices.values() if inv.retention_amount]
    assert withheld, "no invoice carried a retención; the column was dropped"
