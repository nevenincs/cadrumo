"""The questions the desktop's staged-check recording asks, and the backend's answer to each.

The window's fixtures hold no rule: they look ``ledger.staged.check`` up in a recording
keyed by exactly what was asked. The questions are committed under
``dev/fixtures/ledger-staged-check-questions``, one JSON object per line with its
``kind`` (``row`` or ``draft``) and the ``question`` text, as the frontend's capture
writes them. The producer and the test both answer them here, through the real check.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Literal, get_args
from uuid import uuid4

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.external_constants import OutputLanguage
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ..actions_manual import transaction_from_command
from ..models import ManualLedgerTransactionCommand
from ..staged_check import check_draft, check_stored_row
from ..staged_check_contracts import LedgerStagedDraft, LedgerStagedRow, LedgerStagedRowAnswer, StagedBlockerKind
from ..staged_check_words import blocker_words, share_refusal_words

_YEAR = filing_year_envelope().horizon

_REPOSITORY: Final = Path(__file__).resolve().parents[5]
QUESTIONS: Final = _REPOSITORY / "dev/fixtures/ledger-staged-check-questions/questions.jsonl"
NOTE: Final = (
    "What ledger.staged.check answered for each stored movement and staged request the fixtures ask about, keyed "
    "by exactly what was asked. Written by scripts/ledger_staged_check.py from "
    "dev/fixtures/ledger-staged-check-questions."
)
_NOW: Final = datetime(_YEAR, 3, 2, 10, tzinfo=UTC)
_ID: Final = "a" * 64

QuestionKind = Literal["row", "draft"]


@dataclass(frozen=True, slots=True)
class StagedCheckQuestions:
    """The committed questions: stored-row questions and draft questions, each the exact text asked."""

    rows: tuple[str, ...]
    drafts: tuple[str, ...]


def parse_questions(lines: Iterable[str]) -> StagedCheckQuestions:
    """Read question lines, refusing an unknown kind or a question asked twice."""
    asked: dict[QuestionKind, list[str]] = {"row": [], "draft": []}
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        entry = json.loads(line)
        kind = entry.get("kind")
        if kind not in get_args(QuestionKind) or not isinstance(entry.get("question"), str):
            raise ValueError(f"question line {number}: needs a kind of row or draft and a question text")
        if entry["question"] in asked[kind]:
            raise ValueError(f"question line {number}: the {kind} question is asked twice")
        asked[kind].append(entry["question"])
    return StagedCheckQuestions(rows=tuple(asked["row"]), drafts=tuple(asked["draft"]))


def committed_questions() -> StagedCheckQuestions:
    """The questions committed for the recording."""
    return parse_questions(QUESTIONS.read_text(encoding="utf-8").splitlines())


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _optional_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


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
            "operation_date": _optional_date(stored.get("operation_date")),
            "accrual_date": _optional_date(stored.get("accrual_date")),
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
            "deduction_fact_kind": stored["deduction_fact_kind"],
            "investment_asset_id": stored["investment_asset_id"],
            "purchase_invoice_evidence_id": "e" * 64 if question["evidence"] else None,
        }
    )


def row_answer(text: str) -> dict[str, Any]:
    """What the check answers for one stored-row question."""
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


def draft_answer(text: str) -> dict[str, Any]:
    """What the check answers for one draft question."""
    draft = LedgerStagedDraft.model_validate_json(json.dumps({"key": "d", "fields": json.loads(text)}))
    answer = json.loads(check_draft(draft).model_dump_json())
    del answer["key"]
    return answer


def absent_answer() -> dict[str, Any]:
    """What the check answers for a row it cannot find."""
    answer = json.loads(LedgerStagedRowAnswer(transaction_id=_ID, found=False).model_dump_json())
    del answer["transaction_id"]
    return answer


def served_words() -> dict[str, Any]:
    """The sentences the answer carries by kind and language, which depend on nothing else."""
    return {
        "blockers": {
            kind: {
                language.value: dict(zip(("words", "fix_words"), blocker_words(kind, language), strict=True))
                for language in OutputLanguage
            }
            for kind in get_args(StagedBlockerKind)
        },
        "share_refusal": {language.value: share_refusal_words(language) for language in OutputLanguage},
    }


def recording(questions: StagedCheckQuestions) -> dict[str, Any]:
    """The recording: every committed question beside the check's answer to it."""
    return {
        "note": NOTE,
        "absent": absent_answer(),
        "words": served_words(),
        "rows": {question: row_answer(question) for question in sorted(questions.rows)},
        "drafts": {question: draft_answer(question) for question in sorted(questions.drafts)},
    }
