"""The English claim states say dotación, and the missing-form messages say so in plain words."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetClaimState,
    activity_asset_label_key,
)
from cadrumo.core.i18n.render import lookup_translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DOTACION_STATES = (
    ActivityAssetClaimState.CLAIMED,
    ActivityAssetClaimState.MISSING,
    ActivityAssetClaimState.PARTIAL,
    ActivityAssetClaimState.NOT_DUE,
    ActivityAssetClaimState.SUPERSEDED,
)


@pytest.mark.parametrize("state", _DOTACION_STATES)
def test_an_english_claim_state_names_the_dotacion_and_no_claim(state: ActivityAssetClaimState) -> None:
    key = activity_asset_label_key("claim_state", state)
    text = lookup_translation(key, locale="en")

    assert text is not None
    assert "dotaci" in text.lower()
    assert "claim" not in text.lower()


@pytest.mark.parametrize(
    "key",
    [
        "ledger.actividad_asset.errors.tax_year_without_edition",
        "ledger.actividad_asset.errors.claim_year_beyond_registry",
    ],
)
def test_a_missing_form_message_says_the_form_is_not_available_yet_and_names_no_edition(key: str) -> None:
    text = lookup_translation(key, locale="en")

    assert text is not None
    assert "isn't available yet" in text
    assert "Modelo 100 edition" not in text
