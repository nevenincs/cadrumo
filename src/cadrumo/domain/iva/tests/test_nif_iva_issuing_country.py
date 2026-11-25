"""The country a NIF-IVA's prefix names is the issuing State, and nothing else.

Directive 2006/112/EC art. 215 gives an individual identification number for IVA a
prefix in ISO 3166 alpha-2 form that identifies the Member State that issued it,
with Greece using ``EL``. The derivation is a suggestion about where the issuing
State is; it must never answer for a number that does not carry a real prefix,
for a bare Spanish identifier, or for a jurisdiction that has no ISO country.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ..identification import nif_iva_issuing_country

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Synthetic numbers shaped like each State's published VIES structure.
_GERMAN = "DE811234567"
_GREEK = "EL123456789"
_SPANISH_PREFIXED = "ESB00015016"
_SPANISH_BARE = "B00015016"


@pytest.mark.parametrize(
    ("printed", "country"),
    [
        (_GERMAN, "DE"),
        ("de 811 234 567", "DE"),
        ("DE-811.234.567", "DE"),
        # The IVA prefix and the ISO code diverge for Greece; the country is ISO.
        (_GREEK, "GR"),
        # RGAT art. 25: a Spanish identifier in the operators' register is printed with the ES prefix.
        (_SPANISH_PREFIXED, "ES"),
    ],
    ids=["german", "german-spaced", "german-punctuated", "greek-el-is-gr", "spanish-prefixed"],
)
def test_a_prefixed_number_names_the_state_that_issued_it(printed: str, country: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        assert nif_iva_issuing_country(printed, operation=operation) == country


@pytest.mark.parametrize(
    "printed",
    [
        None,
        "",
        # A bare Spanish identifier prints no prefix, so it states no issuing State.
        _SPANISH_BARE,
        "12345678Z",
        # A party name in the field is not a number: two leading letters alone prove nothing.
        "FRANCISCO",
        "DEBITO",
        # The prefix names a State, but the body does not have that State's structure.
        "DE12",
        "ESB99999999",
        # Northern Ireland's XI is an IVA prefix, not an ISO 3166 country.
        "XI123456789",
        # A prefix that names no Member State.
        "US123456789",
    ],
    ids=[
        "absent",
        "empty",
        "spanish-bare-cif",
        "spanish-bare-nif",
        "name-francisco",
        "word-debito",
        "short-body",
        "spanish-wrong-control-letter",
        "northern-ireland",
        "third-country",
    ],
)
def test_anything_but_a_real_prefixed_number_names_no_country(printed: str | None) -> None:
    with bundled_indexed_authority().operation() as operation:
        assert nif_iva_issuing_country(printed, operation=operation) is None
