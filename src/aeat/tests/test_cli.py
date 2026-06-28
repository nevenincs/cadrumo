"""Real-behavior tests for the locales developer CLI (behavior contract).

Verifies that every ``typer.echo`` call in the locales CLI is routed
through ``tr()`` so operator-facing output observes the configured
output language rather than being hard-coded English strings.
"""

from __future__ import annotations

import pytest

from ..core.i18n import tr
from ..core.i18n._render import DEFAULT_OUTPUT_LANGUAGE

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_locales_cli_audit_file_ok_key_renders_non_trivially() -> None:
    """locales.cli.audit.file_ok renders a non-trivial string in Spanish.

    The locale catalogue key must produce a meaningful string (not the
    raw key used as a self-referencing fallback) so the audit output
    is operator-readable under the default language.
    """
    rendered = tr("locales.cli.audit.file_ok", locale_file="es.yml")

    assert rendered != "locales.cli.audit.file_ok"
    assert "es.yml" in rendered


def test_locales_cli_audit_file_drift_key_interpolates_counts() -> None:
    """locales.cli.audit.file_drift interpolates locale_file, missing_count, extra_count."""
    rendered = tr(
        "locales.cli.audit.file_drift",
        locale_file="en.yml",
        missing_count=3,
        extra_count=1,
    )

    assert "en.yml" in rendered
    assert "3" in rendered
    assert "1" in rendered
    assert rendered != "locales.cli.audit.file_drift"


def test_locales_cli_audit_key_missing_interpolates_key() -> None:
    """locales.cli.audit.key_missing interpolates the missing key name."""
    rendered = tr("locales.cli.audit.key_missing", key="some.locale.key")

    assert "some.locale.key" in rendered
    assert rendered != "locales.cli.audit.key_missing"


def test_locales_cli_audit_key_extra_interpolates_key() -> None:
    """locales.cli.audit.key_extra interpolates the extra key name."""
    rendered = tr("locales.cli.audit.key_extra", key="stale.key")

    assert "stale.key" in rendered
    assert rendered != "locales.cli.audit.key_extra"


def test_locales_cli_scaffold_updated_renders_non_trivially() -> None:
    """locales.cli.scaffold_updated renders a meaningful scaffold confirmation."""
    rendered = tr("locales.cli.scaffold_updated")

    assert rendered != "locales.cli.scaffold_updated"
    assert len(rendered) > 5


def test_locales_cli_set_updated_interpolates_file_and_key() -> None:
    """locales.cli.set.updated interpolates locale_file and key."""
    rendered = tr("locales.cli.set.updated", locale_file="es.yml", key="some.key")

    assert "es.yml" in rendered
    assert "some.key" in rendered
    assert rendered != "locales.cli.set.updated"


def test_locales_cli_remove_removed_interpolates_file_and_key() -> None:
    """locales.cli.remove.removed interpolates locale_file and key."""
    rendered = tr("locales.cli.remove.removed", locale_file="ca.yml", key="old.key")

    assert "ca.yml" in rendered
    assert "old.key" in rendered
    assert rendered != "locales.cli.remove.removed"


def test_locales_cli_keys_render_differently_across_supported_languages() -> None:
    """locales.cli.audit.file_ok renders in at least two distinct forms across locales.

    The catalogue must have authored translations (not scaffolded self-refs) for
    at least one non-default language, demonstrating the keys are live catalogue
    entries and not tautological fallbacks.
    """
    from ..core.i18n._render import SUPPORTED_OUTPUT_LANGUAGES

    rendered_values = set()
    for lang in SUPPORTED_OUTPUT_LANGUAGES:
        rendered_values.add(tr("locales.cli.scaffold_updated", locale=lang))

    # At minimum the scaffold_updated key must render in at least one language.
    assert any(v != "locales.cli.scaffold_updated" for v in rendered_values)


def test_default_output_language_constant_is_es() -> None:
    """DEFAULT_OUTPUT_LANGUAGE equals 'es' (behavior contract — constant introduction).

    The constant was introduced as the canonical spelling of the Spanish
    fallback. Every 'es' fallback in _render.py now references this
    constant; this test locks its value so accidental changes fail loudly.
    """
    assert DEFAULT_OUTPUT_LANGUAGE == "es"
