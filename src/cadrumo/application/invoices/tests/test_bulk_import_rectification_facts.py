"""A bulk invoice book can state a factura rectificativa and the facts it carries.

Before these columns the importer wrote every row as an ordinaria, so a book
holding corrections could not express one at all: the class axis had no column,
and the four facts that decide a Modelo 303 modification's sign and period
(RD 1619/2012 art. 15.5, LIVA art. 80, art. 89.Cinco and art. 114.Dos) had
nowhere to go. The class axis and the facts arrive together because they are
refused apart -- a rectification fact on any other class is refused at the
write boundary, so columns for the facts alone could state nothing importable.

Nothing is defaulted: a rectificativa row stating only some of the facts
imports and is blocked where the Modelo 303 would declare it, which these tests
assert through the real production helper rather than by restating the rule.

These tests drive the real reader, the real importer and the real invoice
builder, and read the stored :class:`Invoice` back from the catalogue. No
mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.field_role import FieldRole
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import RectificationFact
from ....domain.invoices.models import Invoice
from ....domain.invoices.rectification import missing_rectification_facts, required_rectification_facts
from ....domain.iva.schema import InvoiceKind
from ..bulk_import import BulkInvoiceImportResult, import_invoices_from_rows, read_bulk_invoice_import_source
from .catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "59595959-5959-4959-8959-595959595959"
_SPANISH_CIF = "B00010157"
_HEADER = "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,country_code"
_RECTIFICATION_HEADER = (
    "invoice_class,series,rectifies_invoice_number,"
    "rectification_method,rectification_cause,rectification_direction,document_received_on"
)


def _issue_date() -> date:
    return date(filing_year_envelope().horizon, 3, 14)


def _served_tokens(on: date) -> tuple[str, str, str]:
    """A method, cause and direction fact 0141 declares for ``on``, read rather than spelled."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=on)
    return (
        str(catalogue.diferencia_token),
        str(catalogue.otra_modificacion_cause_token),
        str(catalogue.minoracion_token),
    )


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


def test_the_rectification_columns_bind_by_their_canonical_header(tmp_path: Path) -> None:
    source_path = tmp_path / "book.csv"
    source_path.write_text(f"{_HEADER},{_RECTIFICATION_HEADER}\n", encoding="utf-8")

    resolution = read_bulk_invoice_import_source(source_path).resolution

    by_header = {column.header: (column.field, column.role, column.source) for column in resolution.columns}
    assert by_header["invoice_class"] == ("invoice_class", FieldRole.INVOICE_CLASS, "exact")
    assert by_header["series"] == ("series", FieldRole.SERIES, "exact")
    assert by_header["rectifies_invoice_number"] == (
        "rectifies_invoice_number",
        FieldRole.RECTIFIES_INVOICE_NUMBER,
        "exact",
    )
    assert by_header["rectification_method"] == ("rectification_method", FieldRole.RECTIFICATION_METHOD, "exact")
    assert by_header["rectification_cause"] == ("rectification_cause", FieldRole.RECTIFICATION_CAUSE, "exact")
    assert by_header["rectification_direction"] == (
        "rectification_direction",
        FieldRole.RECTIFICATION_DIRECTION,
        "exact",
    )
    assert by_header["document_received_on"] == ("document_received_on", FieldRole.DOCUMENT_RECEIVED_ON, "exact")
    assert resolution.unmapped_columns == ()


def test_a_received_rectificativa_row_imports_with_every_fact(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The complete row reaches the catalogue as a rectificativa with nothing left to supply."""
    issued = _issue_date()
    method, cause, direction = _served_tokens(issued)
    received = issued.replace(day=issued.day + 6)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0001,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0001,{method},{cause},{direction},{received.isoformat()}\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert result.refused == ()
    assert result.created == 1
    invoice = stored["R-0001"]
    assert str(invoice.invoice_class) == "RECTIFICATIVA"
    assert invoice.series == "R"
    assert invoice.rectifies_invoice_number == "F-0001"
    assert str(invoice.rectification_method) == method
    assert str(invoice.rectification_cause) == cause
    assert str(invoice.rectification_direction) == direction
    assert invoice.document_received_on == received
    assert missing_rectification_facts(invoice) == ()


def test_a_rectificativa_row_missing_facts_imports_and_stays_blocked(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A partial row is written as stated, with the remaining facts reported absent.

    This is the behaviour the slice turns on: the person's book holds what the
    document said, and the declaration -- not the import -- is what refuses.
    """
    issued = _issue_date()
    method, _, _ = _served_tokens(issued)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0002,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0002,{method},,,\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert result.refused == ()
    invoice = stored["R-0002"]
    assert str(invoice.rectification_method) == method
    assert invoice.rectification_cause is None
    assert invoice.rectification_direction is None
    assert invoice.document_received_on is None
    assert missing_rectification_facts(invoice) == tuple(
        fact
        for fact in required_rectification_facts(InvoiceKind.RECEIVED)
        if fact is not RectificationFact.RECTIFICATION_METHOD
    )


def test_a_rectification_fact_on_an_ordinaria_row_is_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The write boundary's class rule reaches the importer, naming the row and the fact."""
    issued = _issue_date()
    _, cause, _ = _served_tokens(issued)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,F-0003,{issued.isoformat()},1000.00,21,ES,,,,,{cause},,\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert stored == {}
    assert result.created == 0
    assert [(row.row_number, row.field) for row in result.refused] == [(2, "invoice")]
    assert "only applies to a factura rectificativa" in result.refused[0].reason


def test_an_undeclared_rectification_token_is_refused_with_the_served_vocabulary(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The accepted values come from fact 0141, so the refusal lists what the registry carries."""
    issued = _issue_date()

    result, _ = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0004,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0004,,art_80_cinco,,\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert [(row.row_number, row.field) for row in result.refused] == [(2, "rectification_cause")]
    accepted = resolve_invoice_legal_classification_catalogue(
        effective_date=issued,
    ).rectification_cause_choices
    for token in accepted:
        assert str(token) in result.refused[0].reason


def test_a_reception_date_on_an_issued_row_is_refused(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    """An issued rectificativa observes no reception, so the importer cannot record one."""
    issued = _issue_date()
    received = issued.replace(day=issued.day + 6)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER}\n"
        f"{_SPANISH_CIF},Cliente SL,R-0005,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0005,,,,{received.isoformat()}\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert stored == {}
    assert [(row.row_number, row.field) for row in result.refused] == [(2, "invoice")]
    assert "only applies to a received invoice" in result.refused[0].reason


def test_an_ordinaria_row_without_the_columns_is_unchanged(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    """The control: a book with none of these columns imports exactly as it did before."""
    issued = _issue_date()

    result, stored = _import(
        f"{_HEADER}\n{_SPANISH_CIF},Proveedor SL,F-0006,{issued.isoformat()},1000.00,21,ES\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert result.refused == ()
    invoice = stored["F-0006"]
    assert str(invoice.invoice_class) == "ORDINARIA"
    assert invoice.series is None
    assert invoice.rectifies_invoice_number is None
    assert missing_rectification_facts(invoice) == ()
    assert invoice.base_total == Decimal("1000.00")


_ELECTION_HEADER = (
    "issuer_increase_election,issuer_minoracion_election,issuer_minoracion_regularisation_period,"
    "recipient_increase_period,art_80_tres_obligations_attested,exercised_deduction_period"
)


def _elected_period(on: date) -> str:
    """One declaración-liquidación in the canonical display form, named from the row's own year."""
    return str(Period.from_year_and_code(on.year, "2T"))


def test_a_received_row_states_the_recipient_period_election_and_it_reaches_the_record(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """LIVA art. 114.Dos.1.º lets the recipient choose the period, and the book can state that choice."""
    issued = _issue_date()
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=issued)
    method = str(catalogue.diferencia_token)
    cause = str(catalogue.otra_modificacion_cause_token)
    aumento = str(catalogue.aumento_token)
    received = issued.replace(day=issued.day + 6)
    elected = _elected_period(issued)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER},{_ELECTION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0010,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0010,{method},{cause},{aumento},{received.isoformat()},"
        f",,,{elected},,\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert result.refused == ()
    invoice = stored["R-0010"]
    assert invoice.recipient_increase_period is not None
    assert str(invoice.recipient_increase_period) == elected
    assert invoice.issuer_increase_election is None
    assert invoice.art_80_tres_obligations_attested is None


def test_an_issued_row_states_the_minoracion_route_and_the_period_it_regularises_in(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Art. 89.Cinco letter b) names a route and the declaración-liquidación it is regularised in."""
    issued = _issue_date()
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=issued)
    method = str(catalogue.diferencia_token)
    cause = str(catalogue.otra_modificacion_cause_token)
    minoracion = str(catalogue.minoracion_token)
    election = str(catalogue.regularizacion_en_autoliquidacion_token)
    elected = _elected_period(issued)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER},{_ELECTION_HEADER}\n"
        f"{_SPANISH_CIF},Cliente SL,R-0011,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0011,{method},{cause},{minoracion},,"
        f",{election},{elected},,,\n",
        tmp_path,
        kind=InvoiceKind.ISSUED,
        operation=operation,
    )

    assert result.refused == ()
    invoice = stored["R-0011"]
    assert str(invoice.issuer_minoracion_election) == election
    assert invoice.issuer_minoracion_regularisation_period is not None
    assert str(invoice.issuer_minoracion_regularisation_period) == elected


def test_a_calendar_cell_in_an_elected_period_column_is_refused_under_that_column(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A period is a filing year and a registry code, so a date cell refuses rather than resolving one."""
    issued = _issue_date()
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=issued)
    method = str(catalogue.diferencia_token)
    cause = str(catalogue.otra_modificacion_cause_token)
    aumento = str(catalogue.aumento_token)
    received = issued.replace(day=issued.day + 6)

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER},{_ELECTION_HEADER}\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0012,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0012,{method},{cause},{aumento},{received.isoformat()},"
        f",,,{issued.isoformat()},,\n",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert stored == {}
    assert [(row.row_number, row.field) for row in result.refused] == [(2, "recipient_increase_period")]


def test_a_blank_attestation_cell_stays_unanswered_and_a_stated_denial_is_recorded(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Absent holds the art. 80.Tres modification; a stated ``no`` is the denial that refuses it."""
    issued = _issue_date()
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=issued)
    method = str(catalogue.diferencia_token)
    cause = str(catalogue.art_80_tres_cause_token)
    aumento = str(catalogue.aumento_token)
    received = issued.replace(day=issued.day + 6)
    rows = (
        f"{_SPANISH_CIF},Proveedor SL,R-0013,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0013,{method},{cause},{aumento},{received.isoformat()},,,,,,\n"
        f"{_SPANISH_CIF},Proveedor SL,R-0014,{issued.isoformat()},1000.00,21,ES,"
        f"RECTIFICATIVA,R,F-0014,{method},{cause},{aumento},{received.isoformat()},,,,,no,\n"
    )

    result, stored = _import(
        f"{_HEADER},{_RECTIFICATION_HEADER},{_ELECTION_HEADER}\n{rows}",
        tmp_path,
        kind=InvoiceKind.RECEIVED,
        operation=operation,
    )

    assert result.refused == ()
    assert stored["R-0013"].art_80_tres_obligations_attested is None
    assert stored["R-0014"].art_80_tres_obligations_attested is False
