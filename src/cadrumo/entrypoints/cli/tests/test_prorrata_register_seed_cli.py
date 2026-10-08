"""Locale catalogue coverage for prorrata seed and sector-lifecycle copy."""

from __future__ import annotations

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Every user-facing translation key the seed and sector-lifecycle verbs resolve.
_NEW_TRANSLATION_KEYS = (
    "cli.app.ledger.prorrata.seed_help",
    "cli.app.ledger.prorrata.seed_sector_help",
    "cli.app.ledger.prorrata.settle_sector_help",
    "cli.app.ledger.prorrata.seed_ejercicio_help",
    "cli.app.ledger.prorrata.con_derecho_volume_help",
    "cli.app.ledger.prorrata.sin_derecho_volume_help",
    "cli.app.ledger.prorrata.seed_blocked",
    "cli.app.ledger.prorrata.seed_source_absent",
    "cli.app.ledger.prorrata.seed_regulated_override_standing",
    "cli.app.ledger.prorrata.seed_local_authority",
    "cli.app.ledger.prorrata.seed_sector_prior_definitive_absent",
    "cli.app.ledger.prorrata.settle_sector_entry_absent",
)


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("translation_key", _NEW_TRANSLATION_KEYS)
def test_every_supported_locale_resolves_the_new_keys(locale: str, translation_key: str) -> None:
    """A catalogue that echoes the key back has no translation for it."""
    rendered = tr(translation_key, locale=locale)
    assert rendered != translation_key
    assert rendered.strip() != ""
