"""A tax identity printed WITH separators must not survive the funnel either.

The shipped scans anchored on unbroken word characters, so they could never
produce a span containing a hyphen or a space. Both admission gates, meanwhile,
already normalise what they are handed: ``validate_identity`` documents that it
tolerates dashes and spaces, and the prefixed arm calls ``normalise_nif_iva``
before consulting the per-State table. **The tolerant half and the intolerant
half sat on opposite sides of the same funnel**, so the separated spelling was
never rejected by a rule -- it simply never reached one.

That spelling is not exotic. Printed invoices hyphenate and space these
constantly, the OCR and vision route reproduces whatever the page shows, and a
provenance anchor is documented as the verbatim printed form exactly as it
appears. The app itself treats the spellings as one identity: normalisation
folds them together and a shipped gate asserts the spaced form yields the same
establishment key. Only the funnel saw one and not the other.

**The negative half is the load-bearing half.** Admitting separators is what
lets a scan start eating ordinary operator output, and a widening that redacts
an invoice series makes every refusal message unreadable -- a cost paid by every
operator on every command, against a leak that costs nothing until it happens.
The corpus below was built before the pattern, and two of its entries are real
false positives the first attempt produced, found by running the four shipped
locale catalogues through the funnel rather than by reading the regex.
"""

from __future__ import annotations

import pytest

from ..identity import IdentityError, normalise_nif_iva, validate_identity
from ..redaction.rules import redact_for_cli_output, redact_for_log

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Printed renderings of a real tax identity. Every one folds, under the app's
#: own normalisation, onto a form the funnel already redacted.
SEPARATED_IDENTITIES = [
    "SE 556677889901",
    "SE-556677-889901",
    "ESB-1234567-4",
    "B-1234567-4",
    "12.345.678-Z",
    "X-1234567-L",
]

#: Compact spellings, redacted before this change and still redacted after it.
#: Present so a regression that traded one spelling for the other is visible.
COMPACT_IDENTITIES = [
    "SE556677889901",
    "ESB12345674",
    "B12345674",
    "12345678Z",
    "ES B12345674",
]

#: Operator text that must survive untouched. The first two are MEASURED false
#: positives from the first attempt, which admitted the space as a separator: a
#: Hungarian date range normalising to a checksum-valid CIF, and a monetary
#: bound matching the personal-identity arm. The rest are the ordinary
#: hyphenated output a widening threatens.
OPERATOR_TEXT = [
    "A 2020-2024",
    "meghaladja a 6 000 000-t",
    "SE-2026-000412",
    "F-2026-0142",
    "INV-001",
    "2026-0142",
    "2026-03-10",
    "casilla-303",
    "part-002",
    "2022",
    "W09-P17-S257",
    "no-such-thing",
    "modelo303",
    "Barcelona",
    "factura",
    "invoice",
    "ES2024",
    "Total factura 1.234,56 EUR",
    "aeat app ledger evidence extract",
]


@pytest.mark.parametrize("printed", SEPARATED_IDENTITIES)
@pytest.mark.parametrize("funnel", [redact_for_cli_output, redact_for_log])
def test_a_separator_bearing_identity_does_not_survive(printed: str, funnel) -> None:
    """The leak this closes, on both funnels."""
    assert funnel(printed) != printed


@pytest.mark.parametrize("printed", SEPARATED_IDENTITIES)
def test_the_separated_form_names_the_same_bearer_the_compact_one_does(printed: str) -> None:
    """Anti-tautology: the corpus must be real identities, not arbitrary strings.

    Without this the case above passes against a scan that redacts anything
    hyphenated, and the suite would be asserting over-firing rather than
    protection. The app's own normalisation is the authority asked.
    """
    normalised = normalise_nif_iva(printed)

    assert normalised != printed, "the entry must actually carry a separator"
    assert redact_for_cli_output(normalised) != normalised, (
        "the compact form must already redact, or this entry proves nothing about separators"
    )


@pytest.mark.parametrize("printed", COMPACT_IDENTITIES)
def test_the_compact_spelling_still_does_not_survive(printed: str) -> None:
    """The widening must not trade one spelling for the other."""
    assert redact_for_cli_output(printed) != printed


@pytest.mark.parametrize("text", OPERATOR_TEXT)
@pytest.mark.parametrize("funnel", [redact_for_cli_output, redact_for_log])
def test_ordinary_operator_text_survives_untouched(text: str, funnel) -> None:
    """The bound, and the half that pays for itself on every command."""
    assert funnel(text) == text


def test_the_scan_does_not_eat_the_space_in_front_of_an_identity() -> None:
    """A separator at an EDGE is not part of the identity.

    The first attempt put the optional X/Y/Z group's separator outside the
    group, so it could match empty and leave the separator leading the pattern.
    ``for example 12345678Z`` then redacted to ``for examplesha256:...`` and the
    operator's sentence lost a word boundary. The identity is still redacted
    here -- what must survive is the space in front of it.
    """
    redacted = redact_for_cli_output("for example 12345678Z is the shape")

    assert "for example " in redacted, "the space before the identity was consumed"
    assert " is the shape" in redacted
    assert "12345678Z" not in redacted


def test_the_negative_corpus_is_not_vacuous() -> None:
    """A subtraction gate passes trivially when nothing was there to remove.

    Every entry above asserts an ABSENCE, so the suite has to prove the funnel
    is live in the same run. If redaction were disabled wholesale the positive
    cases would fail, but the negative ones would pass in silence and read as
    green.
    """
    removed = sum(1 for printed in SEPARATED_IDENTITIES if redact_for_cli_output(printed) != printed)

    assert removed == len(SEPARATED_IDENTITIES), "the funnel removed nothing; the negative half is measuring nothing"


def test_the_separated_forms_the_gates_reject_are_left_alone() -> None:
    """Normalise-then-match, not a wider pattern: the GATE still decides.

    A hyphenated string that normalises to something no identity authority
    recognises must pass through. This is what distinguishes the shape shipped
    here from simply admitting more characters.
    """
    lookalike = "B-1234567-9"

    with pytest.raises(IdentityError):
        validate_identity(normalise_nif_iva(lookalike))

    assert redact_for_cli_output(lookalike) == lookalike
