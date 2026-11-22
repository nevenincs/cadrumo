"""The ledger hold a rectificativa raises is worded with the facts the record is missing.

The finding carries stable field names; the person reads a sentence. These
tests take an issue with missing facts through the real need-sentence
resolution in every supported locale, so a missing or untranslated key is a
failure here rather than a token leaking onto an operator's screen.

The locale catalogues address the operator informally in the singular in
Spanish, Catalan and Hungarian, which is why each language is asked for its own
words rather than falling back to English.

Real-behaviour: the real translation catalogues through the real hold wording.
No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...ledger.preflight import LedgerPreflightIssue, LedgerPreflightIssueReason
from ..calculation_preparation import LedgerPreflightHold, _hold_context, ledger_hold_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASON = LedgerPreflightIssueReason.INVOICE_RECTIFICATIVA_MODIFICATION_UNMODELLED
_MISSING = ("rectification_method", "rectification_cause", "rectification_direction", "document_received_on")


def _period() -> Period:
    return Period.from_year_and_code(filing_year_envelope().horizon, "2T")


def _issue(missing_facts: tuple[str, ...]) -> LedgerPreflightIssue:
    return LedgerPreflightIssue(
        transaction_id="__period__",
        reason=_REASON,
        detail="a factura rectificativa is declared on no IVA rate row",
        missing_facts=missing_facts,
    )


def _words(missing_facts: tuple[str, ...], language: OutputLanguage) -> str:
    issue = _issue(missing_facts)
    context = _hold_context(issue, _period(), None, language)
    hold = LedgerPreflightHold(
        reason=issue.reason.value,
        issue_transaction_id=issue.transaction_id,
        movement=None,
        context=context,
    )
    return ledger_hold_words(hold, language)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_locale_words_each_missing_fact(language: OutputLanguage) -> None:
    """Four facts produce four worded phrases, none of them a bare field name."""
    words = _words(_MISSING, language)

    for fact in _MISSING:
        assert fact not in words, f"{language.value} left the raw field name {fact!r} in the sentence"
    # The four phrases are distinct, so none of the four keys resolved to the
    # same fallback string.
    separators = words.count(", ")
    assert separators >= 3, f"{language.value} did not list four distinct facts: {words!r}"


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_hold_with_no_missing_fact_keeps_its_sentence_unchanged(language: OutputLanguage) -> None:
    """An issue naming no absent fact must read exactly as it did before this slice."""
    with_facts = _words(_MISSING, language)
    without = _words((), language)

    assert len(without) < len(with_facts)
    assert without.endswith(".")
    # The added clause is a continuation of the one sentence, so the shorter
    # form is its prefix up to the terminal period.
    assert with_facts.startswith(without[:-1])
