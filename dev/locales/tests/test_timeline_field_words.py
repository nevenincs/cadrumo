"""The catalogue holds a word for each fact the activity-asset timeline shows, and for nothing else."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ACTIVITY_ASSET_LABEL_NAMESPACE,
    TIMELINE_FIELD_FAMILY,
    TIMELINE_FIELD_PATHS,
    timeline_field_word_key,
)
from cadrumo.core.external_constants import SUPPORTED_OUTPUT_LANGUAGES

from .._paths import LOCALES_DIR, SRC_DIR
from ..locale_tree import _flatten_raw_locale_leaves
from ..locale_yaml import locale_catalogue_source
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PREFIX = f"{ACTIVITY_ASSET_LABEL_NAMESPACE}{TIMELINE_FIELD_FAMILY}."


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_field_words_are_exactly_the_facts_the_timeline_shows(locale: str) -> None:
    source = locale_catalogue_source(LOCALES_DIR, locale)
    assert source is not None
    leaves = _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, LOCALES_DIR).load_locale(source))

    worded = {key for key in leaves if key.startswith(_PREFIX)}

    assert worded == {timeline_field_word_key(path) for path in TIMELINE_FIELD_PATHS}
