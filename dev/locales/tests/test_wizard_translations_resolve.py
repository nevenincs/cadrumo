"""Locale-coverage gate for the wizard descriptor and the CLI surface.

``audit_wizard_translations`` walks every ``Translatable`` referenced
by :data:`WIZARD_FLOWS`, the descriptor-derived flag-help keys, and
the fixed runtime error keys. ``audit_cli_translations`` walks every
``cli.<group>.*`` key supplied to a ``tr(...)`` call by any module under
``cadrumo.entrypoints.cli``. Both audits assert every key resolves to
non-empty content in every locale.
"""

from __future__ import annotations

import pytest

from dev.locales.wizard_translation_audit import (
    audit_cli_translations,
    audit_wizard_translations,
    cli_keys_referenced_in_source,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_wizard_translation_resolves_in_every_locale() -> None:
    missing = audit_wizard_translations()
    assert missing == ()


def test_every_cli_translation_resolves_in_every_locale() -> None:
    missing = audit_cli_translations()
    assert missing == ()


def test_cli_keys_extracted_from_source_are_non_empty() -> None:
    """The call-site extractor must surface CLI keys used by entrypoints."""

    keys = cli_keys_referenced_in_source()
    assert keys, "no cli.* keys extracted from entrypoint sources"
    # Spot-check: representative keys from distinct namespaces are extracted.
    assert "cli.config.errors.no_active_profile" in keys
    assert "cli.app.modelo.describe.label_title" in keys
    assert "cli.app.live.iva_wallet.acquisition.outcome.aeat_403" in keys
