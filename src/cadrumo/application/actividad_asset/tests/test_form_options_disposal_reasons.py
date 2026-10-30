"""The form options offer exactly the baja reasons the record accepts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetFormOptionsView,
    activity_asset_label_key,
)
from cadrumo.application.actividad_asset.fact_wording import token_family
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from cadrumo.core.i18n.render import I18N_STRICT_MISSING_KEYS, tr
from cadrumo.domain.renta.actividad_asset.disposal import (
    ADMITTED_DISPOSAL_REASONS,
    REFUSED_DISPOSAL_REASONS,
    ActivityAssetDisposalReason,
    require_admissible_disposal,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .operations_support import build_operations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _accepts(reason: ActivityAssetDisposalReason) -> bool:
    try:
        require_admissible_disposal(reason, proceeds=Decimal("0"), transmission_costs=Decimal("0"), market_value=None)
    except ActividadAssetUnsupportedError:
        return False
    return True


def _options(asset_kind: AssetKind = AssetKind.MATERIAL) -> ActivityAssetFormOptionsView:
    return build_operations().form_options(asset_kind=asset_kind, tax_year=2025)


@pytest.mark.parametrize("asset_kind", list(AssetKind))
def test_the_options_offer_every_reason_the_record_accepts_and_no_other(asset_kind: AssetKind) -> None:
    offered = {option.reason for option in _options(asset_kind).disposal_reasons}

    assert offered == {reason for reason in ActivityAssetDisposalReason if _accepts(reason)}
    assert ActivityAssetDisposalReason.DONATION not in offered


def test_the_options_keep_the_declaration_order_of_the_admitted_reasons() -> None:
    assert tuple(option.reason for option in _options().disposal_reasons) == ADMITTED_DISPOSAL_REASONS
    assert set(REFUSED_DISPOSAL_REASONS) == {ActivityAssetDisposalReason.DONATION}


def test_a_refused_reason_is_refused_with_its_own_key() -> None:
    with pytest.raises(ActividadAssetUnsupportedError) as refused:
        require_admissible_disposal(
            ActivityAssetDisposalReason.DONATION,
            proceeds=Decimal("0"),
            transmission_costs=Decimal("0"),
            market_value=None,
        )

    assert refused.value.translated_message == REFUSED_DISPOSAL_REASONS[ActivityAssetDisposalReason.DONATION]


def test_each_option_carries_the_key_that_words_its_reason() -> None:
    family = token_family(ActivityAssetDisposalReason)

    assert [option.label_key for option in _options().disposal_reasons] == [
        activity_asset_label_key(family, reason) for reason in ADMITTED_DISPOSAL_REASONS
    ]


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_offered_reason_has_a_catalogue_word_in_every_locale(locale: str) -> None:
    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        words = [tr(option.label_key, locale=locale) for option in _options().disposal_reasons]
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    assert len(words) == len(ADMITTED_DISPOSAL_REASONS)
    assert all(word.strip() for word in words)
