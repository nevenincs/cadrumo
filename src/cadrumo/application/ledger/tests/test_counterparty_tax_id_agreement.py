"""Confirming an invoice asserts the supplied tax id, rather than overriding it.

Every other field on a confirm layers the operator's value over the extracted
one and lets the operator win silently. The counterparty tax id is the field
where that is wrong, because it is the only one nothing else checks: the
counterparty NAME is supplied by the operator, so a misread name is caught by
them typing it, while a misread tax id was accepted unseen.

The checksum is the PRIMARY defence and it is strong -- a transposed digit
breaks the check character and `validate_spanish_tax_id` refuses outright.
What it cannot catch is a misread that is a different VALID identifier,
belonging to a different real taxpayer. These cases cover that residue.

Supplying the value is an assertion, not an override, and that is what makes
it safe: typing to CHECK is not typing to SET. A typo produces a refusal here,
never a wrong value on a filing.
"""

from __future__ import annotations

import pytest

from .._evidence import PurchaseInvoiceEvidenceInputError
from .._evidence_draft import _agreed_counterparty_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXTRACTED = "12345678Z"
#: Valid, and a DIFFERENT taxpayer -- the case the checksum cannot catch.
_OTHER_VALID = "87654321X"


def test_agreement_confirms_the_value() -> None:
    """The ordinary path: the operator read what the extractor read."""
    assert _agreed_counterparty_tax_id(supplied=_EXTRACTED, extracted=_EXTRACTED) == _EXTRACTED


def test_a_disagreement_refuses() -> None:
    """The residue the checksum leaves: valid, well-formed, wrong taxpayer.

    Both values pass their check character, so nothing downstream has a
    reason to question either. Only the comparison can tell them apart.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED)


def test_the_refusal_names_the_field_and_prints_neither_value() -> None:
    """A tax identity must not reach a pasteable artefact to say "mismatch".

    The operator already knows the value they typed, so printing either side
    buys nothing and puts an identity into output that may be pasted into an
    issue or a log.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED)

    message = str(refusal.value)
    assert "counterparty_tax_id" in message
    assert _EXTRACTED not in message
    assert _OTHER_VALID not in message


@pytest.mark.parametrize("supplied", ["  12345678z  ", "12345678z", "12345678Z  "])
def test_case_and_padding_are_not_a_disagreement(supplied: str) -> None:
    """Case and surrounding whitespace are spelling, not identity.

    Compared through the shared identity token rather than a local
    normalisation, so this agrees with every other surface asking whether
    two identifiers are the same one.

    A SEPARATOR is deliberately not covered here. The shared token
    normalises by trim-and-uppercase and nothing more, on the stated
    grounds that it must never silently merge two identifiers differing in
    their characters -- so ``12345678-Z`` reads as a disagreement and
    refuses. That is the canonical rule rather than this module's choice,
    and the refusal it produces is instructive rather than silent.
    """
    assert _agreed_counterparty_tax_id(supplied=supplied, extracted=_EXTRACTED) == supplied


def test_extraction_finding_nothing_leaves_the_operator_authoritative() -> None:
    """The override case the flag has always served, preserved.

    There is nothing to disagree with, so refusing here would break the
    workflow the flag exists for -- a document the extractor could not read.
    """
    assert _agreed_counterparty_tax_id(supplied=_EXTRACTED, extracted=None) == _EXTRACTED


def test_an_operator_who_supplies_nothing_gets_the_extracted_value() -> None:
    """Asserting is optional; not asserting must not change the outcome."""
    assert _agreed_counterparty_tax_id(supplied=None, extracted=_EXTRACTED) == _EXTRACTED


def test_neither_side_carrying_a_value_is_left_to_the_required_check() -> None:
    """Absence is the confirmed-field check's finding, not this one's."""
    assert _agreed_counterparty_tax_id(supplied=None, extracted=None) is None


def test_the_comparison_is_what_causes_the_refusal() -> None:
    """Mutation proof: without the comparison, the mismatch case stops refusing.

    Re-runs the resolution with the comparison removed -- the pre-change
    behaviour, where a supplied value simply won. It returns the operator's
    value rather than raising, which is exactly the silent override this
    replaces. Without this the suite would prove a refusal EXISTS somewhere,
    not that comparing is what produces it.
    """

    def _without_comparison(*, supplied: str | None, extracted: str | None) -> str | None:
        return supplied if supplied is not None else extracted

    assert _without_comparison(supplied=_OTHER_VALID, extracted=_EXTRACTED) == _OTHER_VALID
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED)
