"""Fail-closed structural contracts for injected Spanish tax-ID declarations."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ..documents import SpanishTaxIdFormat
from .tax_id_format_support import SPANISH_TAX_ID_FORMAT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        pytest.param({"country_prefix": "E1"}, "uppercase ASCII letters", id="country-prefix-non-letter"),
        pytest.param(
            {"prefixed_nif_leaders": "KL\N{GREEK CAPITAL LETTER MU}"},
            "uppercase ASCII letters",
            id="leader-non-ascii",
        ),
        pytest.param({"nif_letters": "TRWAGMYFPDXBNJZSQVHLCKT"}, "23 unique", id="nif-table-duplicate"),
        pytest.param({"nif_letters": "TRWAGMYFPDXBNJZSQVHLCK1"}, "23 unique", id="nif-table-non-letter"),
        pytest.param({"cif_letter_table": "JABCDEFGHJ"}, "ten unique", id="cif-table-duplicate"),
        pytest.param({"cif_letter_table": "JABCDEFGH1"}, "ten unique", id="cif-table-non-letter"),
        pytest.param(
            {"nie_prefix_substitutions": (("X", "\N{ARABIC-INDIC DIGIT ZERO}"), ("Y", "1"), ("Z", "2"))},
            "single decimal digits",
            id="nie-substitution-non-ascii-digit",
        ),
        pytest.param({"cif_digit_only_kinds": "AABEH"}, "must not repeat", id="digit-partition-duplicate"),
        pytest.param({"cif_letter_only_kinds": "PPQRSNW"}, "must not repeat", id="letter-partition-duplicate"),
    ),
)
def test_format_refuses_structurally_malformed_authority_declarations(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(SPANISH_TAX_ID_FORMAT, **changes)


def test_known_grounded_format_satisfies_strict_structure() -> None:
    assert isinstance(replace(SPANISH_TAX_ID_FORMAT), SpanishTaxIdFormat)
