"""A bulk invoice book states each row's IVA treatment, Modelo 349 clave and recargo.

Without these columns an entrega intracomunitaria or an export imported as the
domestic treatment its rate implies, and an issued invoice's recargo de
equivalencia (LIVA art. 156-161) could not be entered at all. These tests drive
the real reader, the real importer and the real invoice builder, and read the
stored :class:`Invoice` back from the catalogue.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.aggregation import IntracomOperationType
from ....core.field_role import FieldRole
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ..bulk_import import BulkInvoiceImportResult, import_invoices_from_rows, read_bulk_invoice_import_source
from .catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "58585858-5858-4858-8858-585858585858"
_FRENCH_IVA_NUMBER = "FR40303265045"
_SPANISH_CIF = "B00010157"
_HEADER = "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,country_code"


def _issue_date() -> date:
    return date(filing_year_envelope().horizon, 3, 14)


def _import(
    text: str,
    tmp_path: Path,
    *,
    kind: InvoiceKind,
    operation: PinnedAuthorityOperation,
) -> tuple[BulkInvoiceImportResult, dict[str, Invoice]]:
    source_path = tmp_path / "book.csv"
    source_path.write_text(text, encoding="utf-8")
    ports = in_memory_catalogue_creation_ports()
    result = import_invoices_from_rows(
        read_bulk_invoice_import_source(source_path),
        bucket_id=_BUCKET_ID,
        kind=kind,
        ports=ports,
        operation=operation,
    )
    stored = {invoice.invoice_number: invoice for invoice in ports.invoice_repository.load()}
    return result, stored


def test_the_new_columns_bind_by_their_canonical_header(tmp_path: Path) -> None:
    source_path = tmp_path / "book.csv"
    source_path.write_text(f"{_HEADER},iva_category,operation_type,recargo_amount\n", encoding="utf-8")

    resolution = read_bulk_invoice_import_source(source_path).resolution

    by_header = {column.header: (column.field, column.role, column.source) for column in resolution.columns}
    assert by_header["iva_category"] == ("iva_category", FieldRole.IVA_CATEGORY, "exact")
    assert by_header["operation_type"] == ("operation_type", FieldRole.OPERATION_TYPE, "exact")
    assert by_header["recargo_amount"] == ("recargo_amount", FieldRole.RECARGO_AMOUNT, "exact")
    assert resolution.unmapped_columns == ()


def test_an_eu_b2b_supply_row_keeps_its_stated_category_and_clave(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER},iva_category,operation_type\n"
        f"{_FRENCH_IVA_NUMBER},Atelier Lumière SARL,EU-0001,{issued},1000.00,,FR,intra_community_supply,E\n"
        f"{_FRENCH_IVA_NUMBER},Atelier Lumière SARL,EU-0002,{issued},500.00,,FR,,e\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert (result.created, result.refused) == (2, ())
    stated = stored["EU-0001"]
    assert stated.iva_category == IvaCategory("intra_community_supply")
    assert stated.operation_type is IntracomOperationType.E
    assert (stated.base_total, stated.iva_total) == (Decimal("1000.00"), Decimal("0.00"))
    clave_only = stored["EU-0002"]
    assert clave_only.operation_type is IntracomOperationType.E
    assert clave_only.iva_category == IvaCategory("intra_community_supply"), "the clave declares its category"


def test_an_intra_community_supply_without_its_clave_is_refused_alone(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER},iva_category,operation_type\n"
        f"{_FRENCH_IVA_NUMBER},Atelier Lumière SARL,EU-0010,{issued},1000.00,,FR,intra_community_supply,\n"
        f"{_SPANISH_CIF},Papeleria Sol SL,ES-0011,{issued},100.00,21,ES,,\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert result.created == 1
    assert [(failure.row_number, failure.field) for failure in result.refused] == [(2, "invoice")]
    assert set(stored) == {"ES-0011"}


def test_an_issued_row_stores_its_recargo_inside_the_total(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER},recargo_amount\n{_SPANISH_CIF},Ferreteria Norte SL,RE-0001,{issued},1000.00,21,ES,52.00\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert (result.created, result.refused) == (1, ())
    invoice = stored["RE-0001"]
    assert invoice.recargo_amount == Decimal("52.00")
    assert invoice.iva_total == Decimal("210.00")
    assert invoice.grand_total == Decimal("1262.00"), "LIVA art. 161: the recargo is charged with the cuota"


def test_an_unknown_category_and_a_negative_recargo_refuse_only_their_rows(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER},iva_category,operation_type,recargo_amount\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,RF-0001,{issued},100.00,21,ES,domestic_luxury,,\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,RF-0002,{issued},100.00,21,ES,,,-5.20\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,RF-0003,{issued},100.00,21,ES,,Z,\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,RF-0004,{issued},100.00,21,ES,,,5.20\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert result.created == 1
    assert [(failure.row_number, failure.field) for failure in result.refused] == [
        (2, "iva_category"),
        (3, "invoice"),
        (4, "operation_type"),
    ]
    assert set(stored) == {"RF-0004"}
    assert stored["RF-0004"].recargo_amount == Decimal("5.20")


def test_a_row_without_the_new_columns_imports_as_before(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER}\n{_SPANISH_CIF},Papeleria Sol SL,PL-0001,{issued},100.00,21,ES\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert (result.created, result.refused) == (1, ())
    invoice = stored["PL-0001"]
    assert (invoice.iva_category, invoice.operation_type, invoice.recargo_amount) == (None, None, None)
    assert (invoice.base_total, invoice.iva_total, invoice.grand_total) == (
        Decimal("100.00"),
        Decimal("21.00"),
        Decimal("121.00"),
    )


def test_a_used_goods_margin_row_keeps_its_stated_category(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    """LIVA art. 135.Dos lets the reseller apply the régimen especial de los bienes usados row by row."""
    issued = _issue_date().isoformat()
    result, stored = _import(
        f"{_HEADER},iva_category\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,REBU-0001,{issued},1500.00,,ES,special_regime_used_goods\n"
        f"{_SPANISH_CIF},Ferreteria Norte SL,ES-0002,{issued},100.00,21,ES,\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert (result.created, result.refused) == (2, ())
    rebu = stored["REBU-0001"]
    assert rebu.iva_category == IvaCategory("special_regime_used_goods")
    assert (rebu.base_total, rebu.iva_total) == (Decimal("1500.00"), Decimal("0.00")), "art. 138: no separate cuota"
    assert stored["ES-0002"].iva_category is None
