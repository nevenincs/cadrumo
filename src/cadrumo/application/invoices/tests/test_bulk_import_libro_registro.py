"""A real libro registro imports fully, under its own column names.

The measured defect this closes: ``ledger invoice import`` demanded fixed
English column names and refused the whole file on anything else. A real Spanish
libro registro carries every field the importer needs — issue date, invoice
number, counterparty, NIF, taxable base, IVA rate — and **not one name matches**,
so a book with nothing wrong with it imported nothing. It also carries retención
columns the importer had no slot for at all, so even after renaming, that
withheld IRPF would have vanished silently.

The mapping is supplied here as data, which is what it is at runtime: the
semantic lane decides one role per column, once per file, and deterministic code
copies the cells. These tests exercise the real reader, the real resolution and
the real catalogue writer; only the role verdict is injected, so no model runs.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import FieldRole
from ....domain.iva import InvoiceKind
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_runtime_profile
from .. import import_invoices_from_rows, read_bulk_invoice_import_source

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"
_BUCKET_ID = "31313131-3131-4131-8131-313131313131"

#: The role of each column of the bundled libro de facturas expedidas, in column
#: order: fecha_expedicion, numero_factura, destinatario, nif_destinatario,
#: base_imponible, tipo_iva, cuota_iva, tipo_retencion, importe_retencion,
#: total_factura.
#:
#: Two columns resolve to a real role the importer has no slot for — the IVA
#: cuota and the printed total, both of which it derives — and ``tipo_retencion``
#: has no role at all, because the vocabulary carries a retención amount but no
#: retención rate. All three must be reported, and none may block the import.
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


#: The rows this book cannot yet create, and the substring naming why. Every one
#: is a domain rule upstream of column mapping, so a change here is a change in
#: what the product accepts, not in what it can read.
_ROWS_REFUSED_BY_DOMAIN_RULES: dict[int, str] = {
    5: "totals must be non-negative",
    6: "must be exactly 9 characters",
    7: "must be exactly 9 characters",
    9: "required field is missing or blank",
}


def _mapper(headers):
    """Supply the libro's column roles, as the semantic lane would."""
    return _LIBRO_ROLES if len(headers) == len(_LIBRO_ROLES) else None


def test_the_libro_registro_is_refused_whole_without_a_mapping() -> None:
    """Control: with no mapping, not one Spanish column resolves.

    This is the measured starting state, and it is what makes the test below
    meaningful — without it, a passing import could simply mean the headers
    happened to match all along.
    """
    from ....domain.invoices.errors import InvoiceValidationError

    with pytest.raises(InvoiceValidationError) as caught:
        read_bulk_invoice_import_source(_LIBRO)
    assert "taxable_base" in str(caught.value)


def test_the_libro_registro_resolves_every_field_under_a_mapping() -> None:
    """Every required importer field is supplied by a Spanish-named column."""
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)

    assert source.resolution.consulted_mapping_lane
    assert {
        "counterparty_nif",
        "counterparty_name",
        "invoice_number",
        "invoice_date",
        "taxable_base",
        "iva_rate",
        "retencion_amount",
    } <= source.resolution.fields_present


def test_the_libro_registro_imports_with_no_column_resolution_failure(tmp_path: Path) -> None:
    """Every one of the book's rows is read, and no row fails on column resolution.

    Four of the eight rows are still refused, and each one is refused by a
    pre-existing domain rule that has nothing to do with reading the file: a
    rectificativa's negative total, two EU IVA identifiers held to the nine-
    character Spanish NIF shape, and a factura simplificada to a consumidor
    final carrying no NIF at all. They are named in
    :data:`_ROWS_REFUSED_BY_DOMAIN_RULES` so this test states which failures it
    is accepting, and would break rather than absorb a new one silently.

    What this test owns is that the file is read at all: every row reaches the
    importer under Spanish column names, and not one refusal says a column could
    not be resolved.
    """
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)
    assert len(source.rows) == 8

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            # The libro registro format carries no country column in either
            # book, so the operator states one for the whole import. It
            # applies to EVERY row, which is why a book carrying foreign
            # counterparties needs the column rather than this flag.
            declared_country="ES",
        )

    assert result.rows == 8
    assert result.created == 4
    assert {failure.row_number for failure in result.refused} == set(_ROWS_REFUSED_BY_DOMAIN_RULES)
    for failure in result.refused:
        assert _ROWS_REFUSED_BY_DOMAIN_RULES[failure.row_number] in failure.reason, failure
        assert "column" not in failure.reason.casefold(), failure


def test_unknown_columns_are_reported_rather_than_refused() -> None:
    """The three columns with no importer slot are named, and cost no row."""
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)

    reported = {column.header for column in source.resolution.unmapped_columns}
    assert reported == {"cuota_iva", "tipo_retencion", "total_factura"}
    assert len(source.rows) == 8
    for row in source.rows:
        assert "cuota_iva" not in row.values


def test_the_retencion_amount_reaches_the_catalogue_invoice(tmp_path: Path) -> None:
    """Retención is carried, not dropped: the withheld IRPF lands on the record.

    The first row of the book withholds 640.80 EUR at 15% on a 4272.00 base. The
    importer previously had no column for it at all, so this figure had nowhere
    to go even once the column names were understood.
    """
    from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository

    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        result = import_invoices_from_rows(
            source,
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            # The libro registro format carries no country column in either
            # book, so the operator states one for the whole import. It
            # applies to EVERY row, which is why a book carrying foreign
            # counterparties needs the column rather than this flag.
            declared_country="ES",
        )
        assert result.created == 4
        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()

    by_number = {invoice.invoice_number: invoice for invoice in catalogue.invoices.values()}
    first = by_number["2025/0142"]
    assert first.base_total == Decimal("4272.00")
    assert first.retention_amount == Decimal("640.80")

    withheld = [inv for inv in catalogue.invoices.values() if inv.retention_amount]
    assert withheld, "no invoice carried a retención; the column was dropped"


def test_an_exact_column_name_is_never_displaced_by_the_mapping() -> None:
    """A canonical header binds deterministically, whatever the mapper proposes.

    The same exact-first rule the statement lane uses: a file already written in
    the product's vocabulary must never depend on a judgement to be read.
    """
    from .._bulk_import_columns import resolve_bulk_import_columns

    headers = ("counterparty_nif", "base_imponible")
    resolution = resolve_bulk_import_columns(
        headers,
        mapper=lambda _headers: (FieldRole.NOTES, FieldRole.TAXABLE_BASE),
        required_fields=frozenset({"taxable_base"}),
    )

    assert resolution.consulted_mapping_lane
    # The mapper proposed NOTES for the canonical column; the exact name holds.
    assert resolution.columns[0].field == "counterparty_nif"
    assert resolution.columns[1].field == "taxable_base"


def test_the_mapping_lane_is_not_consulted_when_exact_names_suffice() -> None:
    """A canonical file is read without any judgement, extra columns and all.

    Consulting the lane here would put a model in the path of a file the product
    can already read, which is both slower and a needless dependency; the extra
    column simply reports.
    """
    from .._bulk_import_columns import resolve_bulk_import_columns

    def _must_not_be_called(_headers):
        raise AssertionError("the mapping lane was consulted for a fully canonical header")

    resolution = resolve_bulk_import_columns(
        ("counterparty_nif", "taxable_base", "bogus"),
        mapper=_must_not_be_called,
        required_fields=frozenset({"counterparty_nif", "taxable_base"}),
    )

    assert not resolution.consulted_mapping_lane
    assert [column.header for column in resolution.unmapped_columns] == ["bogus"]


def test_a_rejected_role_token_leaves_the_column_unmapped_not_the_file_refused() -> None:
    """A role token outside the vocabulary costs its column, never the file.

    The mapping step's allow-list refusal reaches the resolver as nothing more
    than ``UNMAPPED`` for that column, because the positional mapping carries
    roles and no reasons. The operator-facing account of *why* is assembled at
    the command boundary and emitted as a notice; what must hold here is that
    the file still reads and every other column still binds.
    """
    from .._bulk_import_columns import resolve_bulk_import_columns

    resolution = resolve_bulk_import_columns(
        ("fecha_expedicion", "base_imponible", "algo_raro"),
        mapper=lambda _headers: (FieldRole.INVOICE_DATE, FieldRole.TAXABLE_BASE, FieldRole.UNMAPPED),
        required_fields=frozenset({"taxable_base"}),
    )

    assert resolution.columns[0].field == "invoice_date"
    assert resolution.columns[1].field == "taxable_base"
    assert [column.header for column in resolution.unmapped_columns] == ["algo_raro"]


def test_a_role_the_importer_has_no_slot_for_is_reported_with_its_role_intact() -> None:
    """A column understood but unusable is distinguishable from one not understood.

    ``cuota_iva`` maps to a real role the importer derives rather than accepts.
    Keeping the role on the resolved column is what lets the operator be told
    the difference between "we do not know this column" and "we know it and do
    not take it".
    """
    from .._bulk_import_columns import resolve_bulk_import_columns

    resolution = resolve_bulk_import_columns(
        ("base_imponible", "cuota_iva"),
        mapper=lambda _headers: (FieldRole.TAXABLE_BASE, FieldRole.IVA_AMOUNT),
        required_fields=frozenset({"taxable_base"}),
    )

    cuota = resolution.columns[1]
    assert cuota.field is None
    assert cuota.role is FieldRole.IVA_AMOUNT
    assert cuota in resolution.unmapped_columns
