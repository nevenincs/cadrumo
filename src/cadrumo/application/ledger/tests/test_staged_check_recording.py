"""The desktop fixtures' recorded staged-check answers stay what the backend answers.

The window's fixtures hold no rule: they look ``ledger.staged.check`` up in a recording
made here. Set ``CADRUMO_STAGED_CHECK_UNRECORDED`` to a file of questions the fixtures could
not answer, one JSON object per line, to answer them and refresh the recording.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final
from uuid import uuid4

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ..actions_manual import transaction_from_command
from ..models import ManualLedgerTransactionCommand
from ..staged_check import check_draft, check_stored_row
from ..staged_check_contracts import LedgerStagedDraft, LedgerStagedRow, LedgerStagedRowAnswer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_RECORDING: Final = Path(__file__).resolve().parents[5] / (
    "native/desktop/frontend/src/dev/fixtures/ledgerStagedCheck.json"
)
_NOW: Final = datetime(2026, 3, 2, 10, tzinfo=UTC)
_ID: Final = "a" * 64
_NOTE: Final = (
    "What ledger.staged.check answered for each stored movement and staged request the fixtures ask about, keyed "
    "by exactly what was asked. Written and held equal to the live answers by test_staged_check_recording.py."
)


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _stored_transaction(question: dict[str, Any]) -> Transaction:
    stored = question["stored"]
    built = transaction_from_command(
        ManualLedgerTransactionCommand(
            bucket_id=str(uuid4()),
            booked_date=date.fromisoformat(stored["booked_date"]),
            amount=Decimal(stored["amount"]),
            currency=stored["currency"],
            direction=TransactionDirection(stored["direction"]),
            description=stored["description"],
            actor="operator",
            source_command="recording",
        ),
        occurred_at=_NOW,
    )
    raw = built.raw.model_copy(
        update={
            "value_date": None if stored["value_date"] is None else date.fromisoformat(stored["value_date"]),
            "counterparty": stored["counterparty"],
        }
    )
    # The stored facts are taken as they are: a stored row is not put through the writer again.
    return built.model_copy(
        update={
            "raw": raw,
            "lifecycle_state": TransactionLifecycleState(question["lifecycle"]),
            "business_classification": BusinessClassification(stored["business_classification"]),
            "business_pct": _decimal(stored["business_pct"]),
            "category_id": stored["category_id"],
            "usage_ratio_id": stored["usage_ratio_id"],
            "taxable_base": _decimal(stored["taxable_base"]),
            "iva_rate": _decimal(stored["iva_rate"]),
            "iva_amount": _decimal(stored["iva_amount"]),
            "iva_category": stored["iva_category"],
            "irpf_category": stored["irpf_category"],
            "notes": stored["notes"],
            "group_label": stored["group_label"],
            "own_account_id": stored["own_account_id"],
            "counterparty_country": stored["counterparty_country"],
            "counterparty_identification_state": stored["counterparty_identification_state"],
            "purchase_invoice_evidence_id": "e" * 64 if question["evidence"] else None,
        }
    )


def _row_answer(text: str) -> dict[str, Any]:
    question = json.loads(text)
    row = LedgerStagedRow.model_validate_json(
        json.dumps(
            {
                "transaction_id": _ID,
                "cells": question["cells"],
                "evidence_staged": question["evidence_staged"],
                "m210_staged": question["m210_staged"],
            }
        )
    )
    answer = json.loads(check_stored_row(row, _stored_transaction(question)).model_dump_json())
    del answer["transaction_id"]
    return answer


def _draft_answer(text: str) -> list[dict[str, Any]]:
    draft = LedgerStagedDraft.model_validate_json(json.dumps({"key": "d", "fields": json.loads(text)}))
    return json.loads(check_draft(draft).model_dump_json())["blockers"]


def _absent() -> dict[str, Any]:
    answer = json.loads(LedgerStagedRowAnswer(transaction_id=_ID, found=False).model_dump_json())
    del answer["transaction_id"]
    return answer


def _recording() -> dict[str, Any]:
    return json.loads(_RECORDING.read_text(encoding="utf-8"))


def test_every_recorded_answer_is_what_the_backend_answers() -> None:
    recording = _recording()
    assert recording["absent"] == _absent()
    assert recording["rows"], "the recording is empty"
    for question, answer in recording["rows"].items():
        assert _row_answer(question) == answer, question
    for question, blockers in recording["drafts"].items():
        assert _draft_answer(question) == blockers, question


# Defined only when given the questions, since with none there is nothing to record.
if os.environ.get("CADRUMO_STAGED_CHECK_UNRECORDED", "") != "":

    def test_record_the_questions_the_fixtures_could_not_answer() -> None:
        recording = _recording() if _RECORDING.exists() else {"rows": {}, "drafts": {}}
        asked = Path(os.environ["CADRUMO_STAGED_CHECK_UNRECORDED"]).read_text(encoding="utf-8").splitlines()
        for line in asked:
            entry = json.loads(line)
            if entry["kind"] == "row":
                recording["rows"][entry["question"]] = _row_answer(entry["question"])
            else:
                recording["drafts"][entry["question"]] = _draft_answer(entry["question"])
        written = {
            "note": _NOTE,
            "absent": _absent(),
            "rows": dict(sorted(recording["rows"].items())),
            "drafts": dict(sorted(recording["drafts"].items())),
        }
        _RECORDING.write_text(json.dumps(written, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
