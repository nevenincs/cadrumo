"""The English wording of the register's dotación messages uses the Spanish tax term, under unchanged keys."""

from __future__ import annotations

import re

import pytest

from cadrumo.core.i18n.render import lookup_translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NAMESPACE = "ledger.actividad_asset."
_KEYS = (
    "errors.claim_superseded_replay",
    "errors.claim_year_beyond_registry",
    "errors.claim_year_not_after_opening_year",
    "errors.claims_exceed_amortizable_basis",
    "errors.claims_overlap",
    "errors.correction_below_effective_claims",
    "errors.disposal_claim_past_boundary",
    "errors.free_claims_disagree_on_cap",
    "errors.free_claims_exceed_annual_cap",
    "errors.interval_has_different_claim",
    "errors.superseding_claim_changes_interval",
    "claim_state.not_due",
)


@pytest.mark.parametrize("key", _KEYS)
def test_an_english_message_names_the_dotacion_and_no_claim(key: str) -> None:
    text = lookup_translation(_NAMESPACE + key, locale="en")

    assert text is not None
    assert "dotaci" in text
    assert "claim" not in re.sub(r"%\{[^}]*\}", "", text).lower()


@pytest.mark.parametrize("key", _KEYS)
def test_the_key_keeps_its_spanish_wording(key: str) -> None:
    spanish = lookup_translation(_NAMESPACE + key, locale="es")

    assert spanish is not None
    assert spanish != lookup_translation(_NAMESPACE + key, locale="en")
