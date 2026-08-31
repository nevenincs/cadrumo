"""CLI modelo describe localization tests."""

from __future__ import annotations

import pytest

from ....core.i18n.render import SUPPORTED_OUTPUT_LANGUAGES, tr
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------------
# contract — describe label localisation
# ---------------------------------------------------------------------------

_DESCRIBE_LABEL_KEYS: tuple[str, ...] = (
    "cli.app.modelo.describe.label_modelo",
    "cli.app.modelo.describe.label_title",
    "cli.app.modelo.describe.label_official_name",
    "cli.app.modelo.describe.label_tax_domain",
    "cli.app.modelo.describe.label_cadence",
    "cli.app.modelo.describe.label_revision",
    "cli.app.modelo.describe.label_revision_ids",
    "cli.app.modelo.describe.label_periods",
    "cli.app.modelo.describe.label_casillas",
    "cli.app.modelo.describe.label_bindings",
    "cli.app.modelo.describe.label_formulas",
)


def test_describe_label_keys_exist_per_locale() -> None:
    """Every ``describe`` label key renders to non-empty text in every locale.

    The ``tr()`` call must not return the bare key, which would
    indicate a missing catalogue entry.  Each label must also be
    non-empty so the tab-separated rows remain operator-readable.
    """
    violations: list[str] = []
    for key in _DESCRIBE_LABEL_KEYS:
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            rendered = tr(key, locale=locale)
            if not rendered:
                violations.append(f"locale={locale!r} key={key!r}: rendered empty string")
            if rendered == key:
                violations.append(
                    f"locale={locale!r} key={key!r}: tr() returned the key itself; "
                    f"the entry is missing from the {locale} catalogue.",
                )

    assert not violations, "\n".join(violations)


def test_describe_label_keys_distinguish_locales() -> None:
    """Each label renders differently in at least two locales.

    Identical strings across all locales for any given label are a
    signal that the translations are untranslated copies (except for
    terms like 'Modelo' and 'Casillas' that are legitimately identical
    in Spanish and Catalan).
    """
    violations: list[str] = []
    for key in _DESCRIBE_LABEL_KEYS:
        rendered_per_locale = {locale: tr(key, locale=locale) for locale in SUPPORTED_OUTPUT_LANGUAGES}
        unique_renderings = set(rendered_per_locale.values())
        if len(unique_renderings) <= 1:
            violations.append(f"{key}: {rendered_per_locale!r}")

    assert not violations, (
        "Describe label keys rendered identically across all locales; "
        "the translations may all be copy-pasted English:\n" + "\n".join(violations)
    )


def test_describe_output_contains_localized_labels_in_english() -> None:
    """``modelo describe 303`` text output contains English label strings.

    The conftest pins CADRUMO_OUTPUT_LANGUAGE=en for the test suite.
    Each label in the output must match the English catalogue entry
    so a reader can confirm the tr() wiring is live end-to-end.
    """
    result = invoke_cached_cli(["app", "modelo", "describe", "303"])
    assert result.exit_code == 0, result.output

    for key in _DESCRIBE_LABEL_KEYS:
        expected_label = tr(key, locale="en")
        assert expected_label in result.output, (
            f"English label for key {key!r} ({expected_label!r}) not found in describe output:\n{result.output}"
        )


# ---------------------------------------------------------------------------
# contract -- describe BadParameter messages are localized via tr()
# ---------------------------------------------------------------------------


def test_describe_non_period_error_is_localized() -> None:
    """``modelo describe 999`` (no --period) surfaces via the locale key.

    The non-period fallback path at the describe boundary now uses
    ``tr("cli.app.modelo.describe.period_error", message=...)``.
    This test verifies the locale key resolves to a non-empty string and
    the CLI does not surface a Python traceback.
    """
    from ....core.i18n.render import tr

    # Confirm the locale key resolves with a message kwarg — this is the
    # same call the production code makes at the error site.
    rendered = tr("cli.app.modelo.describe.period_error", message="modelo 999 not found")
    assert rendered
    assert "999" in rendered or "not found" in rendered or "error" in rendered.lower()

    # Confirm the CLI path itself does not crash or emit a Traceback.
    result = invoke_cached_cli(["app", "modelo", "describe", "999"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def test_describe_period_error_locale_key_interpolates_message() -> None:
    """The ``cli.app.modelo.describe.period_error`` key interpolates ``message``.

    Verifies that the locale value contains the %{message} interpolation
    slot so callers can pass arbitrary registry error text through.
    """
    from ....core.i18n.render import tr

    sentinel = "sentinel-registry-error-xyz"
    rendered = tr("cli.app.modelo.describe.period_error", message=sentinel)
    assert sentinel in rendered, (
        f"locale key cli.app.modelo.describe.period_error did not interpolate 'message' kwarg; got: {rendered!r}"
    )
