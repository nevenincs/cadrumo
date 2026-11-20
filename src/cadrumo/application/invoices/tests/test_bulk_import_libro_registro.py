"""A libro registro resolves its semantic columns under their own names.

The measured defect this closes: ``ledger invoice import`` demanded fixed
English column names and refused the whole file on anything else. A real Spanish
libro registro carries every field the importer needs — issue date, invoice
number, counterparty, NIF, taxable base, IVA rate — and **not one name matches**,
so a book with nothing wrong with it imported nothing. It also carries retención
columns the importer had no slot for at all, so even after renaming, that
withheld IRPF would have vanished silently.

The mapping is supplied here as data, which is what it is at runtime: the
semantic lane decides one role per column, once per file, and deterministic code
copies the cells. These tests exercise the reader and resolution policy. The
encrypted catalogue writer is covered at the profile persistence adapter seam.
"""

from __future__ import annotations

import pytest

from ....core.decimal.grammar import DecimalSeparator
from ....core.field_role import FieldRole
from ....tests.inventory import FIXTURES_DIR
from ..bulk_import import read_bulk_invoice_import_source

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LIBRO = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_expedidas_2025_2026.csv"

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


def test_unknown_columns_are_reported_rather_than_refused() -> None:
    """The three columns with no importer slot are named, and cost no row."""
    source = read_bulk_invoice_import_source(_LIBRO, mapper=_mapper)

    reported = {column.header for column in source.resolution.unmapped_columns}
    assert reported == {"cuota_iva", "tipo_retencion", "total_factura"}
    assert len(source.rows) == 8
    for row in source.rows:
        assert "cuota_iva" not in row.values


def test_an_exact_column_name_is_never_displaced_by_the_mapping() -> None:
    """A canonical header binds deterministically, whatever the mapper proposes.

    The same exact-first rule the statement lane uses: a file already written in
    the product's vocabulary must never depend on a judgement to be read.
    """
    from ..bulk_import_columns import resolve_bulk_import_columns

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
    from ..bulk_import_columns import resolve_bulk_import_columns

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
    from ..bulk_import_columns import resolve_bulk_import_columns

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
    from ..bulk_import_columns import resolve_bulk_import_columns

    resolution = resolve_bulk_import_columns(
        ("base_imponible", "cuota_iva"),
        mapper=lambda _headers: (FieldRole.TAXABLE_BASE, FieldRole.IVA_AMOUNT),
        required_fields=frozenset({"taxable_base"}),
    )

    cuota = resolution.columns[1]
    assert cuota.field is None
    assert cuota.role is FieldRole.IVA_AMOUNT
    assert cuota in resolution.unmapped_columns


#: The roles an operator would assign to the bundled libro de facturas recibidas
#: (tab separated; FECHA, NUM_FACTURA, PROVEEDOR, NIF, CATEGORIA, BASE, TIPO_IVA,
#: CUOTA_IVA, TOTAL, OBSERVACIONES). The cuota and the total are figures the
#: importer derives rather than accepts, so the operator marks them unused.
_RECIBIDAS = FIXTURES_DIR / "financial" / "tabular-dialects" / "libro_facturas_recibidas_2025_2026.csv"
RECIBIDAS_OPERATOR_ROLES = {
    0: FieldRole.INVOICE_DATE,
    1: FieldRole.INVOICE_NUMBER,
    2: FieldRole.COUNTERPARTY_NAME,
    3: FieldRole.COUNTERPARTY_NIF,
    4: FieldRole.UNMAPPED,
    5: FieldRole.TAXABLE_BASE,
    6: FieldRole.IVA_RATE,
    7: FieldRole.UNMAPPED,
    8: FieldRole.UNMAPPED,
    9: FieldRole.NOTES,
}


def test_operator_roles_read_a_book_no_header_names_without_any_mapping_lane() -> None:
    """The operator's roles alone supply every required field of the recibidas book."""

    def _must_not_be_called(_headers):
        raise AssertionError("the mapping lane was consulted although the operator's roles sufficed")

    source = read_bulk_invoice_import_source(
        _RECIBIDAS, mapper=_must_not_be_called, operator_roles=RECIBIDAS_OPERATOR_ROLES
    )

    assert not source.resolution.consulted_mapping_lane
    assert source.resolution.operator_assigned
    assert [column.source for column in source.resolution.columns] == ["operator"] * 10
    assert len(source.rows) == 10
    # The book writes comma decimals; the operator's roles read it under its own convention.
    assert source.rows[0].values["taxable_base"] == "360,55"
    assert source.decimal_separator == DecimalSeparator.COMMA


def test_a_stated_role_beats_an_exact_header_and_exact_names_fill_what_was_left_unstated() -> None:
    """Operator first: its column wins the field, the exact header that lost is left unmapped."""
    from ..bulk_import_columns import resolve_bulk_import_columns

    resolution = resolve_bulk_import_columns(
        ("counterparty_nif", "taxable_base", "importe_neto", "currency"),
        mapper=None,
        operator_roles={2: FieldRole.TAXABLE_BASE},
    )

    by_header = {column.header: column for column in resolution.columns}
    assert by_header["importe_neto"].field == "taxable_base" and by_header["importe_neto"].source == "operator"
    assert by_header["taxable_base"].field is None and by_header["taxable_base"].source == "unmapped"
    assert by_header["counterparty_nif"].field == "counterparty_nif" and by_header["counterparty_nif"].source == "exact"
    assert by_header["currency"].field == "currency" and by_header["currency"].source == "exact"


def test_a_column_the_operator_marked_unused_is_not_read_by_name_or_by_the_model() -> None:
    """UNMAPPED stated by the operator is final: neither exact matching nor the lane takes the column."""
    from ..bulk_import_columns import resolve_bulk_import_columns

    resolution = resolve_bulk_import_columns(
        ("counterparty_nif", "taxable_base"),
        mapper=lambda _headers: (FieldRole.COUNTERPARTY_NIF, FieldRole.TAXABLE_BASE),
        required_fields=frozenset({"counterparty_nif", "taxable_base", "invoice_date"}),
        operator_roles={1: FieldRole.UNMAPPED},
    )

    assert resolution.consulted_mapping_lane
    assert resolution.columns[1].field is None
    assert resolution.columns[1].source == "operator" and resolution.columns[1].role is FieldRole.UNMAPPED
    assert resolution.columns[0].source == "exact"


def test_the_mapping_lane_fills_only_what_stated_roles_and_exact_names_left_open() -> None:
    """The model is asked only for a still-missing required field, and never overrules the operator."""
    from ..bulk_import_columns import resolve_bulk_import_columns

    asked: list[tuple[str, ...]] = []

    def mapper(headers):
        asked.append(tuple(headers))
        return (FieldRole.NOTES, FieldRole.NOTES, FieldRole.INVOICE_DATE, FieldRole.COUNTERPARTY_NIF)

    resolution = resolve_bulk_import_columns(
        ("a", "b", "fecha", "taxable_base"),
        mapper=mapper,
        required_fields=frozenset({"taxable_base", "invoice_date"}),
        operator_roles={0: FieldRole.COUNTERPARTY_NIF},
    )

    assert len(asked) == 1
    by_header = {column.header: column for column in resolution.columns}
    assert by_header["a"].source == "operator" and by_header["a"].field == "counterparty_nif"
    assert by_header["b"].source == "model" and by_header["b"].field == "notes"
    assert by_header["fecha"].source == "model" and by_header["fecha"].field == "invoice_date"
    # The model's NIF claim for the last column is refused: the exact header and the operator hold those fields.
    assert by_header["taxable_base"].source == "exact" and by_header["taxable_base"].field == "taxable_base"


@pytest.mark.parametrize(
    ("roles", "needle"),
    [
        ({12: FieldRole.NOTES}, "not in the file"),
        ({-1: FieldRole.NOTES}, "not in the file"),
        ({0: FieldRole.GRAND_TOTAL}, "not one the importer accepts"),
        ({0: FieldRole.NOTES, 1: FieldRole.NOTES}, "more than one column"),
    ],
    ids=["beyond-the-file", "negative", "unaccepted-role", "role-twice"],
)
def test_roles_the_file_or_importer_cannot_honour_are_refused_with_a_typed_error(
    roles: dict[int, FieldRole], needle: str
) -> None:
    from ....domain.invoices.errors import InvoiceValidationError
    from ..bulk_import_columns import resolve_bulk_import_columns

    with pytest.raises(InvoiceValidationError) as caught:
        resolve_bulk_import_columns(("a", "b", "c"), operator_roles=roles)
    assert needle in str(caught.value)


def test_a_preview_read_reports_a_missing_required_field_instead_of_refusing_the_book() -> None:
    from ....domain.invoices.errors import InvoiceValidationError

    with pytest.raises(InvoiceValidationError):
        read_bulk_invoice_import_source(_RECIBIDAS)
    source = read_bulk_invoice_import_source(_RECIBIDAS, preview=True)

    assert source.resolution.fields_present == frozenset()
    assert len(source.rows) == 10
