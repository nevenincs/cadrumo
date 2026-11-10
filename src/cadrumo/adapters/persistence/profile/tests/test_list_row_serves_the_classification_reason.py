"""A listed row says whose words its classification reason is, and serves a word for a command's name.

The rows are written by the ledger actions over real secure storage and read
back through the repository, so the reason a list serves is the one stored: the
person's stated reason when one was given, the name of the writing command when
none was, and nothing for a row nobody classified.
"""

from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.ledger.list_operation import ledger_list_row
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .classification_origin_support import BUCKET_ID, NOW_DATE, PERSON, Ledger, composed_ledger

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_COMMAND = "aeat app ledger classify"
_STATED = "Paid by card for the studio's printer paper"


@pytest.fixture
def ledger(tmp_path: Path) -> Generator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _stored_row(
    ledger: Ledger,
    *,
    notes: str = "",
    classification: BusinessClassification = BusinessClassification.BUSINESS,
    source_command: str = _COMMAND,
) -> str:
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=BUCKET_ID,
            booked_date=NOW_DATE,
            amount=Decimal("12.10"),
            direction=TransactionDirection.OUTGOING,
            description="Printer paper",
            business_classification=classification,
            notes=notes,
            actor=PERSON,
            source_command=source_command,
        ),
        ports=ledger.ports,
    )
    return created.ref.transaction_id


def test_a_stated_reason_is_served_as_the_persons_own_words(ledger: Ledger) -> None:
    row = ledger_list_row(ledger.row(_stored_row(ledger, notes=_STATED)), language=OutputLanguage.ES)

    assert row.transaction.classification_reason == _STATED
    assert row.classification_reason_source == "stated"
    assert row.classification_reason_words == ""
    assert row.classification_reason_words_language is None


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_command_fallback_is_served_as_a_word_in_the_asked_language(ledger: Ledger, language: OutputLanguage) -> None:
    row = ledger_list_row(ledger.row(_stored_row(ledger)), language=language)

    assert row.transaction.classification_reason == _COMMAND
    assert row.classification_reason_source == "command"
    assert row.classification_reason_words == tr("application.ledger.reason.served.command", locale=language.value)
    assert row.classification_reason_words not in {"", _COMMAND}
    assert _COMMAND not in row.classification_reason_words
    assert row.classification_reason_words_language is language


def test_every_language_says_the_command_word_in_its_own_words(ledger: Ledger) -> None:
    stored = ledger.row(_stored_row(ledger))

    said = {
        language: ledger_list_row(stored, language=language).classification_reason_words for language in OutputLanguage
    }

    assert len(set(said.values())) == len(OutputLanguage)


def test_a_row_nobody_classified_serves_no_reason(ledger: Ledger) -> None:
    row = ledger_list_row(ledger.row(_stored_row(ledger, classification=BusinessClassification.NOT_YET_PROCESSED)))

    assert row.transaction.classification_reason == ""
    assert row.classification_reason_source == "none"
    assert row.classification_reason_words == ""
    assert row.classification_reason_words_language is None


def test_a_reason_the_person_wrote_about_a_command_is_still_theirs(ledger: Ledger) -> None:
    note = "Re-run of the bank import after the aeat app ledger classify step failed"

    row = ledger_list_row(ledger.row(_stored_row(ledger, notes=note)))

    assert row.classification_reason_source == "stated"
    assert row.transaction.classification_reason == note
