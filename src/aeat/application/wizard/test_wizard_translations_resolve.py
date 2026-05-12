"""Locale-coverage gate for the wizard descriptor and the CLI config surface.

``audit_wizard_translations`` walks every ``Translatable`` referenced
by :data:`WIZARD_FLOWS`, the descriptor-derived flag-help keys, and
the fixed runtime error keys. ``audit_cli_config_translations``
walks every ``cli.config.*`` key referenced statically in
``entrypoints/cli/_config.py``. Both audits assert every key
resolves to non-empty content in every locale.
"""

from __future__ import annotations

import pytest

from aeat.application.wizard._translations import (
    audit_cli_config_translations,
    audit_wizard_translations,
    cli_config_keys_referenced_in_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_every_wizard_translation_resolves_in_every_locale() -> None:
    missing = audit_wizard_translations()
    assert missing == ()


def test_every_cli_config_translation_resolves_in_every_locale() -> None:
    missing = audit_cli_config_translations()
    assert missing == ()


def test_cli_config_keys_extracted_from_source_are_non_empty() -> None:
    """The regex extractor must surface the keys referenced in ``_config.py``."""

    keys = cli_config_keys_referenced_in_source()
    assert keys, "no cli.config keys extracted from _config.py source"
    # Spot-check: a representative pair of literal keys is extracted.
    assert "cli.config.set.help" in keys
    assert "cli.config.errors.no_active_profile" in keys
