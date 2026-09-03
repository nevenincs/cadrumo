"""Locale-coverage gate for the wizard descriptor and the CLI surface.

``audit_wizard_translations`` walks every ``Translatable`` referenced
by :data:`WIZARD_FLOWS`, the descriptor-derived flag-help keys, and
the fixed runtime error keys. ``audit_cli_translations`` walks every
``cli.<group>.*`` key supplied to a ``tr(...)`` call by any module under
``cadrumo.entrypoints.cli``. Both audits assert every key resolves to
non-empty content in every locale.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.locales import wizard_translation_audit
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


def test_cli_key_extractor_harvests_aliased_translation_calls(tmp_path: Path, monkeypatch) -> None:
    """Only aliases of the canonical Cadrumo translation function are live."""
    cli_root = tmp_path / "entrypoints" / "cli"
    cli_root.mkdir(parents=True)
    (cli_root / "alias_fixture.py").write_text(
        "from cadrumo.core.i18n import tr as _tr\n"
        "\n"
        "_tr(\"cli.config.wizard_translation_audit_alias_regression.help\")\n"
        "NEARBY_LITERAL = \"cli.config.wizard_translation_audit_alias_regression.literal\"\n",
        encoding="utf-8",
    )
    (cli_root / "third_party_alias_fixture.py").write_text(
        "from third_party.i18n import tr as _tr\n"
        "\n"
        "_tr(\"cli.config.wizard_translation_audit_third_party_alias_regression.help\")\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(wizard_translation_audit, "SRC_DIR", tmp_path)

    keys = cli_keys_referenced_in_source()

    assert "cli.config.wizard_translation_audit_alias_regression.help" in keys
    assert "cli.config.wizard_translation_audit_alias_regression.literal" not in keys
    assert "cli.config.wizard_translation_audit_third_party_alias_regression.help" not in keys
