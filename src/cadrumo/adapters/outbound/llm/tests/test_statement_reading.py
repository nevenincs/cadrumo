"""The statement reader: its instruction, its reply parsing, and the wired path.

The wired cases read a statement PDF through the real
:class:`~cadrumo.adapters.inbound.financial.providers.pdf_statement.PdfStatementProvider`,
the real reader, the real client and the real grounding stage, with a
recording stand-in for the agent service behind the model-run port. No model
is loaded: each reply is authored by the test, modelled on what a text model
was measured returning for the same page -- including the balances it listed
as movements and the movements it invented -- so the wired path is proven to
keep only what the page prints.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.providers.pdf_statement import PdfStatementProvider
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.ledger.statement_reading import ProposedDirection
from cadrumo.core.model_catalogue import ModelRole
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.tests.inventory import FIXTURES_DIR
from cadrumo.tests.pdf_fixtures import multi_page_text_pdf_bytes
from cadrumo_client.contracts.model_runs import ModelRunBody

from ..statement_reading import (
    LocalStatementReader,
    build_statement_page_prompt,
    parse_statement_page_response,
)
from .model_run_support import IMAGE_LANE, RecordingModelRuns, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_STATEMENT = FIXTURES_DIR / "financial" / "n26" / "n26-savings-2025-01.pdf"


def _movement(booked: str, amount: str | None, description: str, direction: str | None) -> dict[str, object]:
    return {
        "booked_date": booked,
        "value_date": None,
        "description": description,
        "counterparty": None,
        "amount": amount,
        "direction": direction,
        "balance": None,
    }


def _reply(*movements: dict[str, object], currency: str | None = "EUR") -> str:
    return json.dumps(
        {"movements": list(movements), "opening_balance": None, "closing_balance": None, "currency": currency}
    )


#: One reply per page of the statement fixture, in page order, shaped like the
#: local text model's measured replies for the same pages.
_PAGE_REPLIES = (
    _reply(
        _movement("01.01.2025", "+8,55EUR", "Zinsertrag", "in"),
        _movement("01.01.2025", None, "Wertstellung", None),
        _movement("11.01.2025", "-3.000,00EUR", "An Hauptkonto", "out"),
        _movement("13.01.2025", "+4.500,00EUR", "Von Hauptkonto", "in"),
        _movement("20.01.2025", "+3.500,00EUR", "Von Hauptkonto", "in"),
    ),
    _reply(
        _movement("01.01.2025", "+8.000,00EUR", "Dein alter Kontostand +8.000,00EUR", "in"),
        _movement("01.01.2025", "-3.000,00EUR", "Ausgehende Transaktionen -3.000,00EUR", "out"),
        _movement("01.01.2025", "+13.008,55EUR", "Dein neuer Kontostand +13.008,55EUR", "in"),
    ),
    _reply(_movement("01.01.2025", "+8,55EUR", "Gesamt +8,55EUR", "in")),
    _reply(
        _movement("01.01.2025", "100.00", "Zahlung", "out"),
        _movement("01.01.2025", "200.00", "Zahlung", "out"),
    ),
)


def test_the_instruction_names_no_bank_and_carries_the_page_after_the_rules() -> None:
    """The reader is language- and bank-neutral, and the page is delimited from its rules."""
    prompt = build_statement_page_prompt("Compra 02/01/2026 -25,00")

    instructions, page = prompt.split("PAGE TEXT:\n")
    assert page == "Compra 02/01/2026 -25,00"
    assert "Copy every value exactly as printed" in instructions
    for bank in ("N26", "BBVA", "Santander", "CaixaBank", "Revolut", "Kontoauszug"):
        assert bank not in instructions


def test_a_reply_is_kept_in_printed_form_and_non_string_values_are_absent() -> None:
    """A number where a printed form belongs is not the printed form, so it is dropped."""
    page = parse_statement_page_response(
        "```json\n"
        + json.dumps(
            {
                "movements": [
                    {"booked_date": "02/01/2026", "amount": "-25,00", "direction": "OUT", "description": "Compra"},
                    {"booked_date": "03/01/2026", "amount": 25.0, "direction": "sideways"},
                    "not an object",
                ],
                "opening_balance": "100,00",
                "closing_balance": 75,
                "currency": "EUR",
            }
        )
        + "\n```",
    )

    assert page.reply_usable
    first, second = page.movements
    assert (first.amount, first.direction, first.description) == ("-25,00", ProposedDirection.OUT, "Compra")
    assert (second.amount, second.direction) == (None, None)
    assert (page.opening_balance, page.closing_balance, page.currency) == ("100,00", None, "EUR")


def test_a_reply_carrying_no_object_marks_the_page_unusable() -> None:
    """An unparseable reply is reported rather than read as a page with no movements."""
    page = parse_statement_page_response("I could not find any movements.")

    assert not page.reply_usable
    assert page.movements == ()


class _ScriptedAgent:
    """Answer page reads in order and scanned-page transcriptions with one transcription."""

    def __init__(self, *, text_replies: tuple[str, ...], transcription: str = "", empty_transcriptions: int = 0):
        self.text_replies = list(text_replies)
        self.transcription = transcription
        self.empty_transcriptions = empty_transcriptions

    def answer(self, body: ModelRunBody) -> str:
        if body.attachments:
            if self.empty_transcriptions > 0:
                self.empty_transcriptions -= 1
                return ""
            return self.transcription
        return self.text_replies.pop(0)


def _carries_images(body: ModelRunBody) -> bool:
    """Whether the run is a vision run."""
    return bool(body.attachments)


@pytest.fixture
def records(secure_object_test_profile: TestRuntimeProfile) -> Iterator[None]:
    """The real bucket runtime backs the client's cache, usage and run records."""
    _ = secure_object_test_profile
    yield


@contextmanager
def _agent(script: _ScriptedAgent) -> Generator[RecordingModelRuns]:
    with serving_agent(lane=IMAGE_LANE, answer=script.answer) as service:
        yield service


@pytest.mark.usefixtures("records")
def test_the_wired_read_keeps_only_the_movements_the_statement_prints() -> None:
    """Balances, totals and invented movements in the replies never become rows."""
    with _agent(_ScriptedAgent(text_replies=_PAGE_REPLIES)) as service:
        provider = PdfStatementProvider(reader_factory=LocalStatementReader)
        validation = provider.validate_source(_STATEMENT)
        rows = list(provider.ingest(_STATEMENT))

    assert validation.is_valid, validation.warnings
    observed = [(row.raw.booked_date.isoformat(), row.raw.amount, row.direction, row.raw.currency) for row in rows]
    assert observed == [
        ("2025-01-01", Decimal("8.55"), TransactionDirection.INCOMING, "EUR"),
        ("2025-01-11", Decimal("3000.00"), TransactionDirection.OUTGOING, "EUR"),
        ("2025-01-13", Decimal("4500.00"), TransactionDirection.INCOMING, "EUR"),
        ("2025-01-20", Decimal("3500.00"), TransactionDirection.INCOMING, "EUR"),
    ]
    assert sum("dropped" in warning for warning in validation.warnings) == 7
    assert len(service.runs) == len(_PAGE_REPLIES), "each page is read once across validation and ingest"
    assert "Zinsertrag 01.01.2025 +8,55EUR" in service.runs[0][1].prompt
    assert {header.role for header, _ in service.runs} == {ModelRole.TEXT_EXTRACTION.value}
    assert {header.consent for header, _ in service.runs} == {None}
    # Copying printed values has one right answer, so the reader asks for no sampling variety.
    assert {(body.temperature, body.max_output_tokens) for _, body in service.runs} == {(0.0, 4096)}
    assert {row.raw.raw_fields["read_by"] for row in rows} == {"llm:agent-statement-read:configured"}


@pytest.mark.usefixtures("records")
def test_a_scanned_page_is_transcribed_then_read(tmp_path: Path) -> None:
    """A page with no text layer goes to the vision role for text, then to the text role."""
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    script = _ScriptedAgent(
        text_replies=(_reply(), _reply(_movement("05.03.2026", "-4,50 EUR", "Coffee shop", "out"))),
        transcription="Coffee shop 05.03.2026 -4,50 EUR",
    )

    with _agent(script) as service:
        rows = list(PdfStatementProvider(reader_factory=LocalStatementReader).ingest(source))

    assert [(row.raw.booked_date.isoformat(), row.raw.amount, row.raw.raw_fields["page_number"]) for row in rows] == [
        ("2026-03-05", Decimal("4.50"), "2")
    ]
    vision = [header.role for header, body in service.runs if _carries_images(body)]
    assert vision == [ModelRole.VISION_TRANSCRIPTION.value]


@pytest.mark.usefixtures("records")
def test_a_scanned_page_read_back_empty_is_read_again(tmp_path: Path) -> None:
    """A vision read that spent its budget and returned no text is retried, not taken as a blank page."""
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    script = _ScriptedAgent(
        text_replies=(_reply(), _reply(_movement("05.03.2026", "-4,50 EUR", "Coffee shop", "out"))),
        transcription="Coffee shop 05.03.2026 -4,50 EUR",
        empty_transcriptions=1,
    )

    with _agent(script) as service:
        rows = list(PdfStatementProvider(reader_factory=LocalStatementReader).ingest(source))

    assert [(row.raw.booked_date.isoformat(), row.raw.amount) for row in rows] == [("2026-03-05", Decimal("4.50"))]
    assert sum(_carries_images(body) for _, body in service.runs) == 2
