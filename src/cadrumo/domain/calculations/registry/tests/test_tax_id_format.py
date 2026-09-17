"""Strict projection tests for the governed Spanish tax-ID format fact."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.identity.tests.tax_id_format_support import SPANISH_TAX_ID_FORMAT
from ..authority import bundled_indexed_authority
from ..tax_id_format import tax_id_format, tax_id_format_from_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _declarations() -> dict[str, str]:
    format_ = SPANISH_TAX_ID_FORMAT
    return {
        "tax_id.width": str(format_.width),
        "tax_id.country_prefix": format_.country_prefix,
        "tax_id.country_prefixed_width": str(format_.country_prefixed_width),
        "tax_id.country_prefix_strip_width": str(format_.country_prefix_strip_width),
        "tax_id.leaders.prefixed_nif": format_.prefixed_nif_leaders,
        "tax_id.leaders.nie": format_.nie_leaders,
        "tax_id.leaders.cif": format_.cif_leaders,
        "tax_id.check.nif_letters": format_.nif_letters,
        "tax_id.check.cif_digit_only_kinds": format_.cif_digit_only_kinds,
        "tax_id.check.cif_letter_only_kinds": format_.cif_letter_only_kinds,
        "tax_id.check.cif_letter_table": format_.cif_letter_table,
        **{f"tax_id.check.nie_prefix.{leader}": value for leader, value in format_.nie_prefix_substitutions},
    }


def test_projection_refuses_an_unknown_declaration() -> None:
    declarations = _declarations()
    declarations["tax_id.check.unrecognised"] = "operative-looking-value"

    with pytest.raises(ValueError, match="unknown declarations"):
        tax_id_format_from_declarations(declarations)


def test_projection_refuses_a_multi_digit_nie_substitution() -> None:
    declarations = _declarations()
    declarations["tax_id.check.nie_prefix.X"] = "00"

    with pytest.raises(ValueError, match="single decimal digits"):
        tax_id_format_from_declarations(declarations)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        pytest.param(
            "tax_id.check.nie_prefix.X",
            "\N{ARABIC-INDIC DIGIT ZERO}",
            "single decimal digits",
            id="unicode-nie-substitution",
        ),
        pytest.param(
            "tax_id.check.nif_letters",
            "TRWAGMYFPDXBNJZSQVHLCKT",
            "23 unique",
            id="duplicate-nif-table-entry",
        ),
        pytest.param(
            "tax_id.check.cif_letter_table",
            "JABCDEFGHJ",
            "ten unique",
            id="duplicate-cif-table-entry",
        ),
        pytest.param(
            "tax_id.check.cif_digit_only_kinds",
            "AABEH",
            "must not repeat",
            id="duplicate-cif-partition-leader",
        ),
    ),
)
def test_projection_refuses_structurally_malformed_operative_values(key: str, value: str, message: str) -> None:
    declarations = _declarations()
    declarations[key] = value

    with pytest.raises(ValueError, match=message):
        tax_id_format_from_declarations(declarations)


def test_the_published_format_declares_the_identity_policy_tables() -> None:
    """The kernel declares no table, so the published fact must carry every one."""
    with bundled_indexed_authority().operation() as operation:
        published = tax_id_format(operation, effective_date=date.today())

    assert published.nif_letters == "TRWAGMYFPDXBNJZSQVHLCKE"
    assert published.cif_letter_table == "JABCDEFGHI"
    assert published.cif_digit_only_kinds == "ABEH"
    assert published.cif_letter_only_kinds == "PQRSNW"
