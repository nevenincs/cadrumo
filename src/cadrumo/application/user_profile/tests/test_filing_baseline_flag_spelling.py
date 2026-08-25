"""The filing-baseline refusal must name flags the CLI actually accepts.

The refusal it feeds tells an operator to add the named flags and re-run. This
CLI's operator is an autonomous agent that follows that instruction literally,
so a dotted profile path reaching the message is unrecoverable: it does not
parse as an option. These gates tie the refusal's vocabulary to the real
:mod:`cadrumo.application.wizard` option surface.
"""

from __future__ import annotations

import pytest

from ...wizard import SETUP_OPTION_INFOS
from cadrumo.application.user_profile.filing_baseline import _profile_path_flag, missing_filing_baseline_flags

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: A natural person who has declared an IVA regime, and so owes the rest of the
#: IVA block. This is the shape that shipped a dotted path to the operator.
_IVA_BLOCK_OWED = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Ana",
    "identity.surnames": "Garcia Lopez",
    "identity.tax_id": "12345678Z",
    "iva.regime": "GENERAL",
}


def test_the_refusal_names_only_flags_the_cli_accepts() -> None:
    """Every flag this refusal emits parses as a real wizard option."""
    emitted = missing_filing_baseline_flags(_IVA_BLOCK_OWED)
    assert emitted, "fixture no longer reproduces an incomplete IVA block"
    unknown = sorted(flag for flag in emitted if flag not in SETUP_OPTION_INFOS)
    assert not unknown, f"refusal would name flags the CLI does not accept: {unknown}"


def test_no_emitted_flag_carries_path_punctuation() -> None:
    """A dot or underscore means a raw profile path leaked into operator text."""
    emitted = missing_filing_baseline_flags(_IVA_BLOCK_OWED)
    malformed = sorted(flag for flag in emitted if "." in flag or "_" in flag)
    assert not malformed, f"profile paths leaked into flag spellings: {malformed}"


@pytest.mark.parametrize(
    ("path", "flag"),
    [
        ("taxpayer_type.country_of_fiscal_residence", "country-of-fiscal-residence"),
        ("taxpayer_type.representante_fiscal_nif", "representante-fiscal-nif"),
        ("iva.redeme_enrolled", "iva-redeme-enrolled"),
        ("iva.regime", "iva-regime"),
        ("tax_residence.jurisdiction_scope", "tax-residence-jurisdiction-scope"),
    ],
)
def test_namespace_handling_is_not_a_textual_rule(path: str, flag: str) -> None:
    """``taxpayer_type`` drops its namespace where ``iva`` keeps it.

    No textual transform reproduces both, which is why the registry is the sole
    authority and a derived-by-string fallback cannot replace it.
    """
    assert _profile_path_flag(path) == flag


def test_an_unregistered_path_still_yields_a_well_formed_flag() -> None:
    """The fallback may name the wrong flag, but never an unparseable one."""
    derived = _profile_path_flag("nonexistent_namespace.some_field")
    assert "." not in derived
    assert "_" not in derived
