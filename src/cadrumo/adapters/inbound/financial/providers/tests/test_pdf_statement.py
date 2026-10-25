"""The bank-agnostic PDF statement provider, read through a deterministic reader.

The provider's own work is real throughout: ``pdfplumber`` reads the fixture
PDFs, and the anchoring, direction, parsing and reconciliation rules decide
what is imported. Only the model behind the reader port is replaced, by
:class:`.statement_reader_support.LinePatternStatementReader`,
which proposes what a line pattern finds on the synthetic statements and can
add the mistakes the local model was measured making.

The statement fixtures are synthetic documents in one bank's template; they
are test data. Each is paired with hand-written expected rows, an oracle
independent of this provider.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from ......application.ledger.document_transcription import DocumentTranscription
from ......application.ledger.evidence_textlayer import text_layer_transcriber_identity
from ......application.ledger.statement_reading import (
    ProposedDirection,
    ProposedStatementPage,
    StatementReaderPort,
    bind_statement_reader_factory,
)
from ......core.hashing import sha256_hex
from ......domain.transactions.enums import TransactionDirection
from ......tests.inventory import FIXTURES_DIR
from ......tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..base import ParsedLedgerRow
from ..detection import detect_provider
from ..pdf_statement import PdfStatementProvider
from .statement_reader_support import LinePatternStatementReader, invented_movement

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial" / "n26"
_STATEMENTS = (
    ("n26-savings-2024-06.pdf", "n26-savings-2024-06.expected.json"),
    ("n26-savings-2025-01.pdf", "n26-savings-2025-01.expected.json"),
    ("n26-savings-2025-05.pdf", "n26-savings-2025-05.expected.json"),
)
_EXPECTED_ROWS = TypeAdapter(list[dict[str, object]])

#: The fixtures print their balances in German; the reader stand-in is told the labels.
_OPENING = "alter Kontostand"
_CLOSING = "neuer Kontostand"


def _reader(**overrides: object) -> LinePatternStatementReader:
    reader = LinePatternStatementReader(opening_label=_OPENING, closing_label=_CLOSING)
    return replace(reader, **overrides)


def _provider(reader: StatementReaderPort) -> PdfStatementProvider:
    return PdfStatementProvider(reader_factory=lambda: reader)


def _expected(name: str) -> list[tuple[str, str | None, Decimal, str]]:
    rows = _EXPECTED_ROWS.validate_json((_FIXTURES / name).read_text(encoding="utf-8"))
    return [
        (
            str(row["booked_date"]),
            None if row["value_date"] is None else str(row["value_date"]),
            Decimal(str(row["amount"])),
            str(row["currency"]),
        )
        for row in rows
    ]


def _observed(rows: list[ParsedLedgerRow]) -> list[tuple[str, str | None, Decimal, str]]:
    observed = []
    for row in rows:
        raw = row.raw
        signed = raw.amount if row.direction is TransactionDirection.INCOMING else -raw.amount
        value_date = None if raw.value_date is None else raw.value_date.isoformat()
        observed.append((raw.booked_date.isoformat(), value_date, signed, raw.currency))
    return observed


@pytest.mark.parametrize(("fixture", "expected"), _STATEMENTS, ids=[name for name, _ in _STATEMENTS])
def test_each_statement_imports_its_printed_movements_and_reconciles(fixture: str, expected: str) -> None:
    """Every movement matches the hand-written rows, and the printed balances agree."""
    provider = _provider(_reader())
    source = _FIXTURES / fixture

    validation = provider.validate_source(source)
    rows = list(provider.ingest(source))

    assert validation.is_valid, validation.warnings
    assert validation.detected_dialect is not None
    assert "reconciliation=reconciled" in validation.detected_dialect
    assert _observed(rows) == _expected(expected)


def test_balances_totals_and_invented_movements_are_dropped_and_reported() -> None:
    """The measured model mistakes never reach a row, and each is named in the warnings."""
    reader = _reader(
        echo_summary_lines=True,
        invented=(invented_movement(booked_date="01.01.2025", amount="100.00"),),
    )
    provider = _provider(reader)
    fixture, expected = _STATEMENTS[1]

    validation = provider.validate_source(_FIXTURES / fixture)
    rows = list(provider.ingest(_FIXTURES / fixture))

    assert validation.is_valid, validation.warnings
    assert _observed(rows) == _expected(expected)
    dropped = [warning for warning in validation.warnings if "not printed together on one line" in warning]
    assert len(dropped) >= 4
    assert not any("100.00" in warning for warning in validation.warnings), "a warning must not quote values"


def test_a_direction_disagreeing_with_the_printed_sign_is_reported_and_ignored() -> None:
    """A reader that misreads every sign does not change one printed sign, and says so."""
    provider = _provider(_reader(reverse_directions=True))
    fixture, expected = _STATEMENTS[0]

    validation = provider.validate_source(_FIXTURES / fixture)
    rows = list(provider.ingest(_FIXTURES / fixture))

    assert validation.is_valid, validation.warnings
    assert _observed(rows) == _expected(expected)
    assert sum("disagrees with the printed sign" in warning for warning in validation.warnings) == len(rows)


def test_a_sign_the_reader_left_out_is_read_off_the_printed_line() -> None:
    """A proposal copied without its sign still takes the sign the line prints."""
    provider = _provider(_reader(drop_signs=True, reverse_directions=True))
    fixture, expected = _STATEMENTS[2]

    rows = list(provider.ingest(_FIXTURES / fixture))

    assert _observed(rows) == _expected(expected)
    assert {row.raw.raw_fields["direction_source"] for row in rows} == {"printed_sign"}


def test_an_amount_printed_without_any_sign_takes_the_proposed_direction(tmp_path: Path) -> None:
    """A debit or credit column prints no sign, so the reader's direction applies and is recorded."""
    source = tmp_path / "columns.pdf"
    source.write_bytes(
        multi_page_text_pdf_bytes(
            (
                "Opening balance 100,00 EUR",
                "Supplier invoice 05.03.2026 40,00 EUR",
                "Customer payment 06.03.2026 15,00 EUR",
                "Closing balance 75,00 EUR",
            ),
        ),
    )
    reader = LinePatternStatementReader(opening_label="Opening balance", closing_label="Closing balance")

    class _ColumnReader:
        decided_by = reader.decided_by
        transcribe_scanned_pages = reader.transcribe_scanned_pages

        def propose_page(self, transcription: DocumentTranscription) -> ProposedStatementPage:
            page = reader.propose_page(transcription)
            first, second = page.movements
            return replace(
                page,
                movements=(
                    replace(first, direction=ProposedDirection.OUT),
                    replace(second, direction=ProposedDirection.IN),
                ),
            )

    rows = list(_provider(_ColumnReader()).ingest(source))

    assert _observed(rows) == [
        ("2026-03-05", None, Decimal("-40.00"), "EUR"),
        ("2026-03-06", None, Decimal("15.00"), "EUR"),
    ]
    assert {row.raw.raw_fields["direction_source"] for row in rows} == {"reader"}


class _ForgetsFirstMovement:
    """A reader that leaves out the first movement of every page."""

    def __init__(self, inner: LinePatternStatementReader) -> None:
        self._inner = inner
        self.decided_by = inner.decided_by

    def transcribe_scanned_pages(
        self, pdf_bytes: bytes, *, page_numbers: tuple[int, ...], source_content_sha256: str
    ) -> dict[int, DocumentTranscription]:
        return dict(
            self._inner.transcribe_scanned_pages(
                pdf_bytes, page_numbers=page_numbers, source_content_sha256=source_content_sha256
            )
        )

    def propose_page(self, transcription: DocumentTranscription) -> ProposedStatementPage:
        page = self._inner.propose_page(transcription)
        return replace(page, movements=page.movements[1:])


def test_a_missing_movement_contradicts_the_printed_balances_and_refuses_the_statement() -> None:
    """Movements that do not sum from the opening to the closing balance are not imported short."""
    provider = _provider(_ForgetsFirstMovement(_reader()))
    source = _FIXTURES / _STATEMENTS[1][0]

    validation = provider.validate_source(source)

    assert not validation.is_valid
    assert any(
        "the printed balances do not follow from the accepted movements" in warning for warning in validation.warnings
    )


def test_a_statement_without_printed_balances_imports_with_a_review_warning() -> None:
    """No balance to check against is stated, not silently treated as reconciled."""
    provider = _provider(LinePatternStatementReader())
    fixture, expected = _STATEMENTS[0]

    validation = provider.validate_source(_FIXTURES / fixture)

    assert validation.is_valid
    assert validation.detected_dialect is not None
    assert "reconciliation=not_checkable" in validation.detected_dialect
    assert any("no balance the movements could be reconciled against" in w for w in validation.warnings)
    assert _observed(list(provider.ingest(_FIXTURES / fixture))) == _expected(expected)


def test_one_source_is_read_once_across_validation_and_ingest() -> None:
    """Detection's validation and the following ingest share one read."""
    reader = _reader()
    provider = _provider(reader)
    source = _FIXTURES / _STATEMENTS[0][0]

    provider.validate_source(source)
    list(provider.ingest(source))
    provider.validate_source(source)

    assert reader.pages_read == 5


def test_rows_carry_neutral_provenance_and_the_printed_forms() -> None:
    """No bank names the provider, and every row keeps the forms it was parsed from."""
    reader = _reader()
    source = _FIXTURES / _STATEMENTS[1][0]

    rows = list(_provider(reader).ingest(source))

    first = rows[0].raw
    assert first.provenance.provider_name == "PDF provider"
    assert first.provider_transaction_id.startswith("pdf-provider-")
    assert first.raw_fields["amount_printed"] == "+8,55"
    assert first.currency == "EUR"
    assert first.raw_fields["booked_date_printed"] == "01.01.2025"
    assert first.raw_fields["read_by"] == reader.decided_by
    assert first.raw_fields["transcribed_by"] == "pdfplumber"
    assert [row.raw.provenance.source_row_index for row in rows] == list(range(1, len(rows) + 1))


def test_a_source_that_is_not_a_pdf_is_declined_without_a_read(tmp_path: Path) -> None:
    """A tabular export never reaches the statement reader."""
    reader = _reader()
    source = tmp_path / "statement.csv"
    source.write_text("Date,Description,Amount\n2026-04-15,Invoice 1,121.00\n", encoding="utf-8")

    validation = _provider(reader).validate_source(source)

    assert not validation.is_valid
    assert validation.warnings == ("source is not a PDF document",)
    assert reader.pages_read == 0


def test_without_a_bound_reader_a_pdf_is_declined_with_the_reason() -> None:
    """A host that composed no reader states why rather than reporting no match."""
    validation = PdfStatementProvider().validate_source(_FIXTURES / _STATEMENTS[0][0])

    assert not validation.is_valid
    assert validation.warnings == ("no statement reader is installed for PDF statements",)


def test_detection_offers_a_pdf_to_the_bound_reader() -> None:
    """With a composed reader, automatic detection reads a PDF statement."""
    reader = _reader()
    with bind_statement_reader_factory(lambda: reader):
        provider = detect_provider(_FIXTURES / _STATEMENTS[0][0])

    assert isinstance(provider, PdfStatementProvider)


def test_an_unreadable_pdf_is_declined_without_exposing_its_path(tmp_path: Path) -> None:
    """A corrupt PDF is a refusal naming a redacted source, never the operator's path."""
    source = tmp_path / "private-folder-name.pdf"
    source.write_bytes(b"%PDF-1.4\nthis is not a PDF body")

    validation = _provider(_reader()).validate_source(source)

    assert not validation.is_valid
    assert not any("private-folder-name" in warning for warning in validation.warnings)


def _scanned_statement(tmp_path: Path) -> Path:
    """A two-page statement whose second page carries no text layer."""
    source = tmp_path / "scanned.pdf"
    source.write_bytes(
        multi_page_text_pdf_bytes(
            ("Statement 01.03.2026 to 31.03.2026", "Opening balance 100,00 EUR"),
            (),
        ),
    )
    return source


def test_a_page_without_text_is_read_from_its_transcription(tmp_path: Path) -> None:
    """A scanned page is transcribed through the port, then grounded like any page."""
    source = _scanned_statement(tmp_path)
    transcription = DocumentTranscription(
        text="Coffee shop 05.03.2026 -4,50 EUR\nClosing balance 95,50 EUR",
        page_count=1,
        source_content_sha256=sha256_hex(source.read_bytes()),
        transcriber=text_layer_transcriber_identity(),
    )
    reader = LinePatternStatementReader(
        opening_label="Opening balance",
        closing_label="Closing balance",
        scanned={2: transcription},
    )

    rows = list(_provider(reader).ingest(source))

    assert _observed(rows) == [("2026-03-05", None, Decimal("-4.50"), "EUR")]
    assert rows[0].raw.raw_fields["page_number"] == "2"


def test_a_page_that_could_not_be_transcribed_refuses_the_statement(tmp_path: Path) -> None:
    """An unread page would import the statement incomplete, so it is refused."""
    validation = _provider(LinePatternStatementReader()).validate_source(_scanned_statement(tmp_path))

    assert not validation.is_valid
    assert any("carry no text layer and could not be transcribed" in w for w in validation.warnings)
