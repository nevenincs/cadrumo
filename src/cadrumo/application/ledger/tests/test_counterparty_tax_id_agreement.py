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

from ..evidence import PurchaseInvoiceEvidenceInputError
from ..evidence_draft import _agreed_counterparty_tax_id
from ..preconditions import LedgerPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The country recorded for this counterparty. Every case below is domestic
#: unless it says otherwise, which is what makes the prefix cases at the end
#: readable as the exception they are.
_COUNTRY = "ES"

_EXTRACTED = "12345678Z"
#: Valid, and a DIFFERENT taxpayer -- the case the checksum cannot catch.
_OTHER_VALID = "87654321X"


def test_agreement_confirms_the_value() -> None:
    """The ordinary path: the operator read what the extractor read."""
    assert (
        _agreed_counterparty_tax_id(supplied=_EXTRACTED, extracted=_EXTRACTED, counterparty_country=_COUNTRY)
        == _EXTRACTED
    )


def test_a_disagreement_refuses() -> None:
    """The residue the checksum leaves: valid, well-formed, wrong taxpayer.

    Both values pass their check character, so nothing downstream has a
    reason to question either. Only the comparison can tell them apart.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED, counterparty_country=_COUNTRY)


def test_the_refusal_carries_the_tax_id_fact_without_printing_either_value() -> None:
    """A mismatch remains typed and never puts either tax id into output.

    The operator already knows the value they typed, so printing either side
    buys nothing and puts an identity into output that may be pasted into an
    issue or a log.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED, counterparty_country=_COUNTRY)

    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID.value
    fact_values = [evidence.values for evidence in verdict.evidence]
    assert any(values.get("counterparty_tax_id_matches_document") is False for values in fact_values)

    message = str(refusal.value)
    assert _EXTRACTED not in message
    assert _OTHER_VALID not in message


@pytest.mark.parametrize("supplied", ["  12345678z  ", "12345678z", "12345678Z  "])
def test_case_and_padding_are_not_a_disagreement(supplied: str) -> None:
    """Case and surrounding whitespace are spelling, not identity.

    Compared through the shared identity token rather than a local
    normalisation, so this agrees with every other surface asking whether
    two identifiers are the same one.

    A SEPARATOR was deliberately not covered here when this was written, on
    the grounds that the shared IDENTITY TOKEN normalises by trim-and-uppercase
    and nothing more. That paragraph is now stale and is corrected rather than
    deleted, because it recorded a real constraint that has since moved: the
    comparison changed to the same-BEARER predicate, which strips separators
    precisely so a printed ``B-1234567-4`` matches a stored ``B12345674``. The
    token's rule is unchanged and still right for KEYING; comparing is a
    different question and now has a different answer. The separator case is
    covered with the prefix cases at the end of this module.
    """
    assert (
        _agreed_counterparty_tax_id(supplied=supplied, extracted=_EXTRACTED, counterparty_country=_COUNTRY) == supplied
    )


def test_extraction_finding_nothing_leaves_the_operator_authoritative() -> None:
    """The override case the flag has always served, preserved.

    There is nothing to disagree with, so refusing here would break the
    workflow the flag exists for -- a document the extractor could not read.
    """
    assert _agreed_counterparty_tax_id(supplied=_EXTRACTED, extracted=None, counterparty_country=_COUNTRY) == _EXTRACTED


def test_an_operator_who_supplies_nothing_gets_the_extracted_value() -> None:
    """Asserting is optional; not asserting must not change the outcome."""
    assert _agreed_counterparty_tax_id(supplied=None, extracted=_EXTRACTED, counterparty_country=_COUNTRY) == _EXTRACTED


def test_neither_side_carrying_a_value_is_left_to_the_required_check() -> None:
    """Absence is the confirmed-field check's finding, not this one's."""
    assert _agreed_counterparty_tax_id(supplied=None, extracted=None, counterparty_country=_COUNTRY) is None


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
        _agreed_counterparty_tax_id(supplied=_OTHER_VALID, extracted=_EXTRACTED, counterparty_country=_COUNTRY)


# ── the country-prefix axis ────────────────────────────────────────────────
#
# The second axis of the same over-refusal. A document routinely states an
# identifier in its IVA form while an operator supplies the bare national form,
# and those name one bearer -- but the discount is safe only against THIS
# counterparty's own country, because the same national body can exist under
# two different country prefixes.
#
# Handled at this call site rather than inside the shared same-bearer
# predicate, which is also consumed by the identity-role resolver and the
# document-direction deriver: a looser rule there would silently change who
# counts as the taxpayer on every document read.

_NATIONAL = "B12345674"
_IVA_FORM = "ESB12345674"


@pytest.mark.parametrize(
    ("supplied", "extracted"),
    [(_NATIONAL, _IVA_FORM), (_IVA_FORM, _NATIONAL)],
    ids=["operator-bare-document-prefixed", "operator-prefixed-document-bare"],
)
def test_the_iva_form_and_the_national_form_are_one_bearer(supplied: str, extracted: str) -> None:
    """The measured over-refusal, in both directions.

    Symmetric on purpose: an operator is as likely to type the prefixed form
    from a VIES lookup as the bare one from a stored profile, so a fix
    discounting only the document's side would refuse half the population it
    was written for.
    """
    assert (
        _agreed_counterparty_tax_id(
            supplied=supplied,
            extracted=extracted,
            counterparty_country=_COUNTRY,
        )
        is not None
    )


def test_the_separator_and_prefix_axes_hold_together() -> None:
    """Both at once, which is the shape a printed document actually produces."""
    assert (
        _agreed_counterparty_tax_id(
            supplied="B-1234567-4",
            extracted="ES B12345674",
            counterparty_country=_COUNTRY,
        )
        is not None
    )


def test_a_foreign_prefix_against_a_spanish_counterparty_still_refuses() -> None:
    """The precision half, and the reason this is not a blanket strip.

    A German-prefixed number on a counterparty recorded in Spain names a
    different bearer and must keep disagreeing.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed_counterparty_tax_id(
            supplied=_NATIONAL,
            extracted="DE12345674",
            counterparty_country=_COUNTRY,
        )


def test_the_discount_follows_the_counterpartys_own_country_never_a_hardcoded_spain() -> None:
    """A French counterparty stating FR against its bare form is the same situation.

    Hardcoding Spain would fix the domestic population and leave every other
    one refusing, which is the shape a Spanish-first codebase produces by
    default and the reason the country is an input rather than a constant.
    """
    assert (
        _agreed_counterparty_tax_id(
            supplied="12345678901",
            extracted="FR12345678901",
            counterparty_country="FR",
        )
        is not None
    )
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        _agreed_counterparty_tax_id(
            supplied="12345678901",
            extracted="ES12345678901",
            counterparty_country="FR",
        )
