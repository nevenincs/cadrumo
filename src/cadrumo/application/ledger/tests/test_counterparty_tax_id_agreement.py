"""Two spellings of one bearer must not be refused as a mismatch.

The confirm path compares the operator's ``--counterparty-nif`` against what the
on-host extractor read, and refuses when they disagree. That refusal is right,
and it was over-firing on two axes rather than one.

The separator axis was fixed first: printed identifiers carry hyphens and spaces
routinely, so ``B-1234567-4`` and ``B12345674`` are one identifier, and the
canonical same-bearer predicate normalises them.

**The country prefix is the second axis, and it is handled at the call site
rather than in that predicate.** A document routinely states an identifier in its
VAT form while an operator supplies the bare national form -- ``ESB12345674``
against ``B12345674``. The shared predicate cannot discount that safely:
stripping a leading alpha-2 unconditionally would merge bearers ACROSS States,
because the same national body can exist under two prefixes, and that predicate
is also consumed by the identity-role resolver and the document-direction
deriver, where a looser rule would silently change who counts as the taxpayer on
every document read.

So the prefix is discounted only when it names THIS counterparty's own country --
a fact the confirm site has and the predicate does not. The tests below assert
both halves: the over-refusal is gone, and the cross-State case still refuses.
"""

from __future__ import annotations

import pytest

from .._evidence_draft import (
    PurchaseInvoiceEvidenceInputError,
    _agreed_counterparty_tax_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NATIONAL = "B12345674"
_VAT_FORM = "ESB12345674"


def _agreed(supplied: str | None, extracted: str | None, *, country: str = "ES") -> str | None:
    return _agreed_counterparty_tax_id(
        supplied=supplied,
        extracted=extracted,
        counterparty_country=country,
    )


@pytest.mark.parametrize(
    ("supplied", "extracted"),
    [(_NATIONAL, _VAT_FORM), (_VAT_FORM, _NATIONAL)],
    ids=["operator-bare-document-prefixed", "operator-prefixed-document-bare"],
)
def test_the_vat_form_and_the_national_form_are_one_bearer(supplied: str, extracted: str) -> None:
    """The measured over-refusal, in both directions.

    Symmetric on purpose: the operator is as likely to type the prefixed form
    from a VIES lookup as the bare one from a stored profile, and a fix that
    only discounted the document's side would refuse half the population it was
    written for.
    """
    assert _agreed(supplied, extracted) is not None


def test_the_separator_axis_still_holds_alongside_the_prefix_one() -> None:
    """Both axes at once, which is the shape a printed document actually produces."""
    assert _agreed("B-1234567-4", "ES B12345674") is not None


def test_a_foreign_prefix_against_a_spanish_counterparty_still_refuses() -> None:
    """The precision half, and the whole reason this is not a blanket strip.

    A German-prefixed number on a counterparty recorded in Spain names a
    different bearer, and must keep disagreeing. A rule that stripped any
    leading alpha-2 would merge them, because the same national body can exist
    under two different country prefixes.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed(_NATIONAL, "DE12345674")


def test_a_genuinely_different_identifier_still_refuses() -> None:
    """The guard is narrowed, not removed: a real mismatch is still a refusal."""
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed(_NATIONAL, "B87654321")


def test_the_prefix_is_discounted_against_the_counterpartys_own_country_not_spain() -> None:
    """The rule is 'this counterparty's country', never a hardcoded ES.

    A French counterparty stating ``FR`` against its own bare form is the same
    situation as the Spanish one, and hardcoding Spain would fix the domestic
    population and leave every other one refusing.
    """
    assert _agreed("12345678901", "FR12345678901", country="FR") is not None
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed("12345678901", "ES12345678901", country="FR")


def test_one_side_absent_still_short_circuits() -> None:
    """The override cases the flag has always served are untouched."""
    assert _agreed(None, _VAT_FORM) == _VAT_FORM
    assert _agreed(_NATIONAL, None) == _NATIONAL
    assert _agreed(None, None) is None
