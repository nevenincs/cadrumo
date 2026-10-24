"""The on-host statement reader: its instruction, its reply parsing, and the wired path.

The wired cases stand up a real loopback endpoint speaking the runtime's
``/api/chat`` wire shape and read a statement PDF through the real
:class:`~cadrumo.adapters.inbound.financial.providers.pdf_statement.PdfStatementProvider`,
the real reader, the real client and the real grounding stage. No model is
loaded: each reply is authored by the test, modelled on what the local text
model was measured returning for the same page -- including the balances it
listed as movements and the movements it invented -- so the wired path is
proven to keep only what the page prints.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import ClassVar, override

import pytest

from cadrumo.adapters.inbound.financial.providers.pdf_statement import PdfStatementProvider
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.ledger.statement_reading import ProposedDirection
from cadrumo.core.config import load_settings, override_settings
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.tests.inventory import FIXTURES_DIR
from cadrumo.tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from cadrumo.tests.pdf_fixtures import multi_page_text_pdf_bytes

from ..evidence_draft_vision import VISION_TRANSCRIPTION_PROMPT_ID, LocalVisionDocumentTranscriber
from ..statement_reading import (
    STATEMENT_READING_PROMPT_ID,
    LocalStatementReader,
    build_statement_page_prompt,
    parse_statement_page_response,
)
from .load_headroom_support import admitting_client

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


def _messages(body: dict[str, object]) -> list[dict[str, object]]:
    """Return the request's message objects."""
    messages = body.get("messages")
    return [message for message in messages if isinstance(message, dict)] if isinstance(messages, list) else []


def _carries_images(body: dict[str, object]) -> bool:
    """Whether the request is a vision request."""
    return any(message.get("images") for message in _messages(body))


def _prompt(body: dict[str, object]) -> str:
    """Return the request's prompt text."""
    return "".join(str(message.get("content", "")) for message in _messages(body))


class _ScriptedRuntime(SilentLoopbackHandler):
    """A real local endpoint holding both reader models.

    It answers text requests in order and vision requests with a transcription.
    """

    text_replies: ClassVar[Queue[str]]
    transcription: ClassVar[str] = ""
    empty_transcriptions: ClassVar[int] = 0
    requests: ClassVar[Queue[dict[str, object]]]

    @override
    def do_GET(self) -> None:
        if self.path != "/api/tags":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        settings = load_settings()
        models = (settings.cadrumo_llm_ollama_text_model, settings.cadrumo_llm_ollama_vision_model)
        write_json_response(self, {"models": [{"name": name, "size": 1} for name in models]}, status=HTTPStatus.OK)

    @override
    def do_POST(self) -> None:
        body = dict(read_json_body(self))
        self.requests.put(body)
        if _carries_images(body):
            content = "" if _ScriptedRuntime.empty_transcriptions > 0 else self.transcription
            _ScriptedRuntime.empty_transcriptions = max(0, _ScriptedRuntime.empty_transcriptions - 1)
        else:
            content = self.text_replies.get_nowait()
        write_json_response(self, ollama_chat_reply(content, model=str(body.get("model"))), status=HTTPStatus.OK)


@pytest.fixture
def runtime(secure_object_test_profile: TestRuntimeProfile) -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    """Serve the scripted runtime on loopback; the real bucket runtime backs the client's records."""
    _ = secure_object_test_profile
    requests: Queue[dict[str, object]] = Queue()
    _ScriptedRuntime.requests = requests
    _ScriptedRuntime.empty_transcriptions = 0
    _ScriptedRuntime.text_replies = Queue()
    for reply in _PAGE_REPLIES:
        _ScriptedRuntime.text_replies.put(reply)
    with serving_loopback(_ScriptedRuntime, path="/api/chat") as chat_url:
        yield chat_url, requests


def _reader() -> LocalStatementReader:
    settings = load_settings()
    client = admitting_client(
        settings.cadrumo_llm_ollama_text_model,
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.statement_reading",
        prompt_id=STATEMENT_READING_PROMPT_ID,
    )
    vision = LocalVisionDocumentTranscriber(
        settings=settings,
        client=admitting_client(
            settings.cadrumo_llm_ollama_vision_model,
            settings=settings,
            caller="cadrumo.adapters.outbound.llm.evidence_draft_vision",
            prompt_id=VISION_TRANSCRIPTION_PROMPT_ID,
        ),
    )
    return LocalStatementReader(settings=settings, client=client, vision_transcriber=vision)


def test_the_wired_read_keeps_only_the_movements_the_statement_prints(
    runtime: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Balances, totals and invented movements in the replies never become rows."""
    chat_url, requests = runtime
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        provider = PdfStatementProvider(reader_factory=_reader)
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
    sent = [requests.get_nowait() for _ in range(requests.qsize())]
    assert len(sent) == len(_PAGE_REPLIES), "each page is read once across validation and ingest"
    assert "Zinsertrag 01.01.2025 +8,55EUR" in _prompt(sent[0])
    assert {body["think"] for body in sent} == {False}


def test_a_scanned_page_is_transcribed_on_host_then_read(
    runtime: tuple[str, Queue[dict[str, object]]],
    tmp_path: Path,
) -> None:
    """A page with no text layer goes to the vision model for text, then to the text model."""
    chat_url, requests = runtime
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    _ScriptedRuntime.transcription = "Coffee shop 05.03.2026 -4,50 EUR"
    _ScriptedRuntime.text_replies = Queue()
    _ScriptedRuntime.text_replies.put(_reply())
    _ScriptedRuntime.text_replies.put(_reply(_movement("05.03.2026", "-4,50 EUR", "Coffee shop", "out")))

    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        rows = list(PdfStatementProvider(reader_factory=_reader).ingest(source))

    assert [(row.raw.booked_date.isoformat(), row.raw.amount, row.raw.raw_fields["page_number"]) for row in rows] == [
        ("2026-03-05", Decimal("4.50"), "2")
    ]
    sent = [requests.get_nowait() for _ in range(requests.qsize())]
    assert sum(_carries_images(body) for body in sent) == 1


def test_a_scanned_page_read_back_empty_is_read_again(
    runtime: tuple[str, Queue[dict[str, object]]],
    tmp_path: Path,
) -> None:
    """A vision read that spent its budget and returned no text is retried, not taken as a blank page."""
    chat_url, requests = runtime
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    _ScriptedRuntime.transcription = "Coffee shop 05.03.2026 -4,50 EUR"
    _ScriptedRuntime.empty_transcriptions = 1
    _ScriptedRuntime.text_replies = Queue()
    _ScriptedRuntime.text_replies.put(_reply())
    _ScriptedRuntime.text_replies.put(_reply(_movement("05.03.2026", "-4,50 EUR", "Coffee shop", "out")))

    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        rows = list(PdfStatementProvider(reader_factory=_reader).ingest(source))

    assert [(row.raw.booked_date.isoformat(), row.raw.amount) for row in rows] == [("2026-03-05", Decimal("4.50"))]
    sent = [requests.get_nowait() for _ in range(requests.qsize())]
    assert sum(_carries_images(body) for body in sent) == 2
