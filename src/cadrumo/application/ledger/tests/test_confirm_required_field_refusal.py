"""A required field neither side states refuses, rather than reaching the catalogue.

This property used to be gated at the CLI, by omitting the counterparty name
from a generated text PDF the reader could recover none from. That suite now
feeds a bundled STRUCTURED document so it can run without a live model, and a
structured document names its parties -- so the state is no longer constructible
there, and the case moved rather than survived.

It belongs here anyway, and arguably always did. The property is a claim about
the confirm service's own behaviour when the draft it is handed lacks a field,
which a constructed pair of arguments states directly. Rebuilding it around a
document would put a reader, an evidence store and a model between the test and
the one line it is about.

**The counterparty name is the field with no fallback, and that asymmetry is the
point.** The tax id has a checksum and a role resolver; the currency has a
documented default; the name has neither, so a document naming nobody and an
operator supplying nothing is the one combination that must refuse rather than
mint a record with an empty party. An invoice reaches Modelo 347 per
counterparty, so an empty name is not a cosmetic gap.
"""

from __future__ import annotations

import pytest

from ..confirmed_field_resolution import _confirmed_counterparty_name
from ..evidence_errors import PurchaseInvoiceEvidenceInputError
from ..preconditions import LedgerPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_neither_side_stating_a_name_refuses() -> None:
    """The motivating case: no extraction, no override, no record."""
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        _confirmed_counterparty_name(None, None)

    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE.value
    fact_values = [evidence.values for evidence in verdict.evidence]
    assert any(values.get("counterparty_name_available") is False for values in fact_values)


def test_the_refusal_carries_the_typed_precondition_rather_than_prose_alone() -> None:
    """What makes the refusal actionable to a surface rather than only readable.

    A caller projecting this to an operator needs the condition that failed, not
    a sentence to pattern-match. Asserted on the condition id and the recorded
    fact, so a refusal that kept its wording while losing its verdict fails
    here -- which is the direction that degrades silently, because the message
    still reads correctly.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        _confirmed_counterparty_name(None, None)

    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None, "the refusal carried no verdict, so no surface can project it"
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE.value
    recorded = [values for evidence in verdict.evidence for values in [evidence.values]]
    assert any(values.get("counterparty_name_available") is False for values in recorded), (
        f"the verdict does not record which field was unavailable: {recorded}"
    )


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n  "])
def test_a_blank_name_is_treated_as_absent_on_both_sides(blank: str) -> None:
    """Whitespace is not a name, whichever side supplies it.

    Parametrised over both arguments rather than one: a guard that stripped the
    operator's value and trusted the reader's would mint a record whose party is
    a tab character, and the reader is the side more likely to produce one --
    a stray cell in a structured document arrives as whitespace, not as None.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _confirmed_counterparty_name(blank, None)
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _confirmed_counterparty_name(None, blank)
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _confirmed_counterparty_name(blank, blank)


def test_the_read_name_is_used_when_the_operator_supplies_nothing() -> None:
    """The positive control the refusals are meaningless without.

    Without this the whole module is satisfiable by a function that refuses
    always, which is the failure mode a refusal test cannot detect about itself.
    """
    assert _confirmed_counterparty_name(None, "Mayorista Ejemplo SL") == "Mayorista Ejemplo SL"


def test_the_operator_override_wins_over_what_was_read() -> None:
    """Extraction is best-effort, so a supplied name corrects it rather than losing to it."""
    assert _confirmed_counterparty_name("Corrected SL", "Misread SL") == "Corrected SL"


def test_a_surrounding_whitespace_name_is_kept_but_trimmed() -> None:
    """A real name padded by the reader is a name, not a refusal.

    The boundary between this and the blank cases is the whole reason the guard
    strips before testing rather than after: refusing a padded value would send
    an operator to correct a name the document states perfectly well.
    """
    assert _confirmed_counterparty_name(None, "  Acme Suministros SL  ") == "Acme Suministros SL"
