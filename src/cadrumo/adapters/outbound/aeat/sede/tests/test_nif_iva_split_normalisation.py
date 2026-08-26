"""The VIES prefix/number split, on the canonical NIF-IVA normal form.

``_split_vies_nif`` once restated the normalisation locally and stripped spaces
and hyphens but NOT dots. That is not a different normal form, it is the
canonical one weaker by one separator -- and the separator it dropped is the one
:func:`~core.identity.normalise_nif_iva` names in its own docstring as the
routine case, because operators paste ``BE 0123.456.789``.

**The dotted case is the load-bearing fixture.** Every other variant passed
under the local form too, so a suite without it would have stayed green while
the defect shipped: the dots survived into ``iva_number`` and were sent to VIES
verbatim.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .._nif_iva_check import _split_vies_nif

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

#: The country prefix and number every printed variant below denotes.
_EXPECTED = ("BE", "0123456789")


@pytest.mark.parametrize(
    "printed",
    (
        pytest.param("BE0123456789", id="compact"),
        pytest.param("BE 0123.456.789", id="dotted-and-spaced"),
        pytest.param("BE0123.456.789", id="dotted"),
        pytest.param("BE-0123-456-789", id="hyphenated"),
        pytest.param("BE 0123 456 789", id="spaced"),
        pytest.param("  be0123456789  ", id="lowercase-padded"),
    ),
)
def test_a_printed_iva_number_splits_to_one_prefix_and_number(printed: str) -> None:
    assert _split_vies_nif(printed) == _EXPECTED


def test_the_dotted_form_carries_no_separator_into_the_number() -> None:
    """The regression this file exists for, stated as its own proposition.

    A dot surviving into ``iva_number`` is not a cosmetic defect: the value is
    sent to VIES as the number to check, so the query asks about an identifier
    no registry holds and the answer is a refusal the operator cannot explain.
    """
    _, iva_number = _split_vies_nif("BE 0123.456.789")
    assert "." not in iva_number
    assert iva_number.isdigit()


@pytest.mark.parametrize(
    "malformed",
    (
        pytest.param("", id="empty"),
        pytest.param("BE", id="prefix-only"),
        pytest.param("B1", id="too-short"),
        pytest.param("---", id="separators-only"),
        pytest.param("12345678", id="no-country-prefix"),
        pytest.param("B-0123456789", id="single-letter-prefix"),
    ),
)
def test_a_value_that_is_not_a_prefixed_iva_number_is_refused(malformed: str) -> None:
    # The negative controls. Normalising more aggressively must not turn a
    # malformed value into an acceptable one -- stripping separators shortens
    # the string, so a value that was long enough before may not be after, and
    # the refusals have to survive the change that made this file necessary.
    with pytest.raises(RegistryValidationError):
        _split_vies_nif(malformed)


def test_the_refusal_names_the_value_as_the_operator_typed_it() -> None:
    # The message quotes the RAW input rather than the normalised form, so an
    # operator can recognise what they pasted. Normalising first must not cost
    # that, and the fixture is chosen so the two forms DIFFER: "b-1" normalises
    # to "B1", so a message built from the normalised value would not match.
    with pytest.raises(RegistryValidationError, match=r"b-1"):
        _split_vies_nif("b-1")
