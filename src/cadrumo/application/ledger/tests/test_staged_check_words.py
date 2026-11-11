"""The staged-work check serves its own sentences for what holds a movement back.

Each kind of blocker is reached through the real check, over a stored movement
or a draft, so the sentence is the one the check hands a window.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import get_args
from uuid import uuid4

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ..actions_manual import transaction_from_command
from ..models import ManualLedgerTransactionCommand
from ..staged_check import check_staged_work
from ..staged_check_contracts import (
    LedgerStagedBlocker,
    LedgerStagedCell,
    LedgerStagedCheckRequest,
    LedgerStagedCheckResult,
    LedgerStagedDraft,
    LedgerStagedDraftField,
    LedgerStagedRow,
    StagedBlockerKind,
)

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_NOW = datetime(_YEAR, 3, 2, 10, tzinfo=UTC)
_ID = "a" * 64

_TOKEN = re.compile(r"[a-z]+_[a-z_]+")
_PLACEHOLDER = re.compile(r"%\{|\{|\}")
_OPTION = re.compile(r"(?<!\w)--[a-z]")


def _stored(
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    category_id: str | None = None,
) -> Transaction:
    return transaction_from_command(
        ManualLedgerTransactionCommand(
            bucket_id=str(uuid4()),
            booked_date=date(_YEAR, 3, 2),
            amount=Decimal("36.30"),
            currency="EUR",
            direction=direction,
            description="SUMINISTRO",
            business_classification=classification,
            category_id=category_id,
            actor="operator",
            source_command="test",
        ),
        occurred_at=_NOW,
    )


def _row(*cells: tuple[str, str | None]) -> LedgerStagedRow:
    return LedgerStagedRow(
        transaction_id=_ID,
        cells=tuple(LedgerStagedCell.model_validate({"field": field, "value": value}) for field, value in cells),
    )


def _draft(**fields: str) -> LedgerStagedDraft:
    return LedgerStagedDraft(
        key="d",
        fields=tuple(LedgerStagedDraftField.model_validate({"field": k, "value": v}) for k, v in fields.items()),
    )


def _blockers_of(
    result: LedgerStagedCheckResult,
) -> dict[StagedBlockerKind, LedgerStagedBlocker]:
    found = [blocker for answer in result.rows for blocker in answer.blockers]
    found += [blocker for answer in result.drafts for blocker in answer.blockers]
    return {blocker.kind: blocker for blocker in found}


def _check(language: OutputLanguage, authority: PinnedAuthorityOperation) -> LedgerStagedCheckResult:
    """One request that reaches every kind of blocker, answered by the real check."""
    profile = uuid4()
    held = {
        "a" * 64: _stored(),
        "b" * 64: _stored(classification=BusinessClassification.BUSINESS),
        "c" * 64: _stored(classification=BusinessClassification.BUSINESS, category_id="office_supplies"),
        "d" * 64: _stored(classification=BusinessClassification.BUSINESS),
        "e" * 64: _stored(direction=TransactionDirection.INCOMING, classification=BusinessClassification.BUSINESS),
    }
    rows = (
        # Clearing a booked date: no write takes a blank date.
        LedgerStagedRow(
            transaction_id="a" * 64,
            cells=(
                LedgerStagedCell(field="booked_date", value=None),
                # A category on a movement with no classification has no write to go to.
                LedgerStagedCell(field="category_id", value="office_supplies"),
            ),
        ),
        # Mixed with no share stored or staged.
        LedgerStagedRow(
            transaction_id="b" * 64, cells=(LedgerStagedCell(field="business_classification", value="MIXED"),)
        ),
        # A share on a movement that is not Mixed.
        LedgerStagedRow(transaction_id="d" * 64, cells=(LedgerStagedCell(field="business_pct", value="0.5"),)),
        # A transfer that still carries a category.
        LedgerStagedRow(
            transaction_id="c" * 64, cells=(LedgerStagedCell(field="direction", value="INTERNAL_TRANSFER"),)
        ),
        # A received invoice whose declared base and IVA stand above the cash:
        # only a declared withholding category accepts that gap.
        LedgerStagedRow(
            transaction_id="e" * 64,
            cells=(
                LedgerStagedCell(field="taxable_base", value="35.00"),
                LedgerStagedCell(field="iva_amount", value="7.35"),
            ),
        ),
    )
    request = LedgerStagedCheckRequest(
        profile_id=profile,
        rows=rows,
        # A new movement with nothing filled in, and one whose amount carries a sign.
        drafts=(_draft(), _draft(amount="-50.00")),
        output_language=language,
    )
    return check_staged_work(request, held, operation=authority, profile_id=profile)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_kind_of_blocker_serves_its_sentences_in_the_language_asked(
    language: OutputLanguage, authority_operation: PinnedAuthorityOperation
) -> None:
    blockers = _blockers_of(_check(language, authority_operation))
    assert set(blockers) == set(get_args(StagedBlockerKind))
    for kind, blocker in blockers.items():
        assert blocker.words_language is language, kind
        for sentence in (blocker.words, blocker.fix_words):
            assert sentence.strip() == sentence and sentence, kind
            # A sentence is finished text: no placeholder, no raw token, no command option.
            assert not _PLACEHOLDER.search(sentence), (kind, sentence)
            assert not _TOKEN.search(sentence), (kind, sentence)
            assert not _OPTION.search(sentence), (kind, sentence)
            # It names none of the private facts the check was asked about.
            for private in ("SUMINISTRO", "36.30", "office_supplies", _ID):
                assert private not in sentence, (kind, sentence)
        assert blocker.words != blocker.fix_words, kind


def test_every_sentence_differs_between_the_languages_and_the_result_names_its_share_sentence(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    by_language = {language: _check(language, authority_operation) for language in OutputLanguage}
    for kind in get_args(StagedBlockerKind):
        for pick in ("words", "fix_words"):
            said = {getattr(_blockers_of(result)[kind], pick) for result in by_language.values()}
            assert len(said) == len(OutputLanguage), (kind, pick)
    for language, result in by_language.items():
        assert result.share_refusal_words_language is language
        assert not _PLACEHOLDER.search(result.share_refusal_words)
        assert not _TOKEN.search(result.share_refusal_words)
    assert len({result.share_refusal_words for result in by_language.values()}) == len(OutputLanguage)


def test_the_sentences_follow_the_kind_and_not_what_was_staged(authority_operation: PinnedAuthorityOperation) -> None:
    profile = uuid4()
    first = check_staged_work(
        LedgerStagedCheckRequest(profile_id=profile, drafts=(_draft(amount="10"),)),
        {},
        operation=authority_operation,
        profile_id=profile,
    )
    second = check_staged_work(
        LedgerStagedCheckRequest(profile_id=profile, drafts=(_draft(amount="9999", description="OTHER"),)),
        {},
        operation=authority_operation,
        profile_id=profile,
    )
    assert first.drafts[0].blockers[0].kind == "draft_incomplete"
    assert first.drafts[0].blockers[0].words == second.drafts[0].blockers[0].words
    assert first.drafts[0].blockers[0].fix_words == second.drafts[0].blockers[0].fix_words
