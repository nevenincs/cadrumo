"""The two canonical tax-identifier normal forms, and the axis that separates them.

:mod:`core.identity` deliberately exports two functions that both "normalise a
tax identifier", and three production sites reached for the wrong one because
nothing here said which. This module is that gate.

**The distinction is separators, not case.** Both forms trim and uppercase, so
every case-only fixture passes under either and proves nothing. The one input
that discriminates is an identifier printed WITH separators against the same
identifier stored compactly -- the shape an on-host extractor really reads off a
printed invoice.

* :func:`same_tax_identifier` answers "same bearer?" on the separator-stripped
  form, so ``B-1234567-4`` and ``B12345674`` are one identifier.
* :func:`tax_id_identity_token` stays trim-and-uppercase because it KEYS stored
  objects: merging two characters-differ identifiers would collapse two
  taxpayers into one row.

**The load-bearing half is the negative.** Each test asserting the predicate
matches is paired with an assertion that the KEYING token does NOT -- so the
suite fails if a future author "simplifies" a comparison site back onto the
token. A test proving only that the predicate matches would stay green through
exactly the regression this exists to catch, because the token matches every
case-only fixture too.
"""

from __future__ import annotations

import pytest

from .._tax_id import same_tax_identifier, tax_id_identity_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The compact stored form every printed variant below denotes.
_STORED = "B12345674"

#: Printed forms carrying each separator :func:`normalise_nif_iva` strips.
#: These are the shapes a document really prints, not invented variants: the
#: hyphenated form is the one the redaction funnel established as routine.
_PRINTED_VARIANTS = (
    pytest.param("B-1234567-4", id="hyphenated"),
    pytest.param("B 1234567 4", id="spaced"),
    pytest.param("B.1234567.4", id="dotted"),
    pytest.param("  b-1234567-4  ", id="lowercase-padded-hyphenated"),
)


@pytest.mark.parametrize("printed", _PRINTED_VARIANTS)
def test_a_printed_identifier_is_the_same_bearer_as_its_stored_form(printed: str) -> None:
    assert same_tax_identifier(printed, _STORED)
    assert same_tax_identifier(_STORED, printed), "the predicate must be symmetric"


@pytest.mark.parametrize("printed", _PRINTED_VARIANTS)
def test_the_keying_token_does_not_merge_the_printed_form(printed: str) -> None:
    # The teeth. This is the assertion that fails if a comparison site is
    # swapped back onto the keying token, and it is why the fixtures above
    # carry separators rather than case alone.
    assert tax_id_identity_token(printed) != tax_id_identity_token(_STORED)


def test_the_two_forms_disagree_on_exactly_this_input() -> None:
    # States the divergence as one proposition, so the reason the codebase
    # carries two functions is executable rather than only documented.
    printed = "B-1234567-4"
    assert same_tax_identifier(printed, _STORED)
    assert tax_id_identity_token(printed) != tax_id_identity_token(_STORED)


@pytest.mark.parametrize(
    "other",
    (
        pytest.param("B12345675", id="differs-in-control"),
        pytest.param("B12345684", id="differs-in-body"),
        pytest.param("A12345674", id="differs-in-leader"),
    ),
)
def test_a_genuinely_different_identifier_is_not_the_same_bearer(other: str) -> None:
    # The negative control: without it, a predicate that answered True for
    # everything would pass every test above.
    assert not same_tax_identifier(other, _STORED)
    assert not same_tax_identifier(f"{other[:1]}-{other[1:8]}-{other[8:]}", _STORED)


@pytest.mark.parametrize(
    ("left", "right"),
    (
        pytest.param(None, _STORED, id="left-absent"),
        pytest.param(_STORED, None, id="right-absent"),
        pytest.param(None, None, id="both-absent"),
        pytest.param("", _STORED, id="left-blank"),
        pytest.param(_STORED, "", id="right-blank"),
        pytest.param("   ", _STORED, id="blank-after-trim"),
        pytest.param("-", _STORED, id="separators-only"),
    ),
)
def test_nothing_to_compare_is_never_the_same_bearer(left: str | None, right: str | None) -> None:
    # Absence must not read as agreement: a caller refusing on mismatch would
    # otherwise silently accept a record carrying no identifier at all.
    assert not same_tax_identifier(left, right)


@pytest.mark.parametrize(
    ("left", "right"),
    (
        pytest.param("", "", id="both-empty"),
        pytest.param("   ", "", id="both-blank-one-padded"),
        pytest.param("-", ".", id="both-separators-only"),
    ),
)
def test_two_blanks_are_not_the_same_bearer(left: str, right: str) -> None:
    """Two absent identifiers are not one identifier, and this is a DECLARED change.

    Called out on its own rather than folded into the set above because it is
    the case that changes behaviour at a live call site. A comparison written as
    ``token(left) != token(right)`` answers "same" for two blanks, because both
    normalise to the empty string -- so a caller refusing on mismatch would
    CONFIRM a record whose identity nothing supplied. Routing that site onto
    this predicate makes it refuse instead.

    Two values that are each nothing are not evidence of agreement, and a
    surface asking "is this the identifier the document carries" must not answer
    yes when neither side carries one.
    """
    assert not same_tax_identifier(left, right)


def test_the_keying_token_is_idempotent() -> None:
    # A normal form that is not idempotent produces a different storage key on
    # re-normalisation, which splits one taxpayer's rows across two keys.
    once = tax_id_identity_token("  b12345674  ")
    assert once == _STORED
    assert tax_id_identity_token(once) == once
