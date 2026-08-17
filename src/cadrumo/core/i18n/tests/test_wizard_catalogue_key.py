"""Catalogue coverage for wizard navigation labels."""

from __future__ import annotations

import pytest

from cadrumo.core.i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NEXT_LOCALE_KEY = "application.wizard.output_labels.next"


@pytest.mark.parametrize("locale", ("en", "es", "ca", "hu"))
def test_wizard_next_locale_key_resolves(locale: str) -> None:
    """The wizard next-label key exists in every shipped catalogue."""
    result = tr(_NEXT_LOCALE_KEY, locale=locale)

    assert result and result != _NEXT_LOCALE_KEY
