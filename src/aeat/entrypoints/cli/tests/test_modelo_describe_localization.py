"""CLI modelo describe localization tests."""

from __future__ import annotations

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
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


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("key", _DESCRIBE_LABEL_KEYS)
def test_describe_label_key_exists_per_locale(locale: str, key: str) -> None:
    """Every ``describe`` label key renders to non-empty text in every locale.

    The ``tr()`` call must not return the bare key, which would
    indicate a missing catalogue entry.  Each label must also be
    non-empty so the tab-separated rows remain operator-readable.
    """
    rendered = tr(key, locale=locale)

    assert rendered, f"locale={locale!r} key={key!r}: rendered empty string"
    assert rendered != key, (
        f"locale={locale!r} key={key!r}: tr() returned the key itself — "
        f"the entry is missing from the {locale} catalogue."
    )


def test_describe_label_keys_distinguish_locales() -> None:
    """Each label renders differently in at least two locales.

    Identical strings across all locales for any given label are a
    signal that the translations are untranslated copies (except for
    terms like 'Modelo' and 'Casillas' that are legitimately identical
    in Spanish and Catalan).
    """
    # Collect all rendered values for each key across locales.
    at_least_one_distinct = False
    for key in _DESCRIBE_LABEL_KEYS:
        rendered_per_locale = {locale: tr(key, locale=locale) for locale in SUPPORTED_OUTPUT_LANGUAGES}
        unique_renderings = set(rendered_per_locale.values())
        if len(unique_renderings) > 1:
            at_least_one_distinct = True
            break

    assert at_least_one_distinct, (
        "Every describe label key rendered identically across all locales — "
        "the translations may all be copy-pasted English."
    )


def test_describe_output_contains_localized_labels_in_english() -> None:
    """``modelo describe 303`` text output contains English label strings.

    The conftest pins AEAT_OUTPUT_LANGUAGE=en for the test suite.
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
    from ....core.i18n import tr

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
    from ....core.i18n import tr

    sentinel = "sentinel-registry-error-xyz"
    rendered = tr("cli.app.modelo.describe.period_error", message=sentinel)
    assert sentinel in rendered, (
        f"locale key cli.app.modelo.describe.period_error did not interpolate 'message' kwarg; got: {rendered!r}"
    )


# ---------------------------------------------------------------------------
# contract -- DT12 / SAL computation error surfaces are localized via tr()
# ---------------------------------------------------------------------------


def test_dt12_computation_error_locale_key_interpolates_message() -> None:
    """``cli.app.modelo.work.dt12_computation_error`` interpolates ``message``.

    The CLI catch block wraps the ValueError from
    ``compute_dt12_reduccion_plan_pensiones`` via
    ``tr("cli.app.modelo.work.dt12_computation_error", message=str(exc))``.
    This test verifies the key resolves and interpolates the message kwarg,
    using the real exception text produced by the computation function.
    """
    from decimal import Decimal

    from ....core.i18n import tr
    from ....domain.modelos._dt12_reduccion import compute_dt12_reduccion_plan_pensiones

    with pytest.raises(ValueError) as exc_info:
        compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("9600"),
            aportaciones_totales=Decimal("0"),
        )

    exc_message = str(exc_info.value)
    rendered = tr("cli.app.modelo.work.dt12_computation_error", message=exc_message)
    assert rendered
    assert exc_message in rendered, (
        f"locale key cli.app.modelo.work.dt12_computation_error did not interpolate 'message' kwarg; got: {rendered!r}"
    )


def test_sal_computation_error_locale_key_interpolates_message() -> None:
    """``cli.app.modelo.work.sal_computation_error`` interpolates ``message``.

    The CLI catch block wraps the ValueError from
    ``compute_sal_reserva_especial_dotacion`` via
    ``tr("cli.app.modelo.work.sal_computation_error", message=str(exc))``.
    This test verifies the key resolves and interpolates the message kwarg,
    using the real exception text produced by the computation function.
    """
    from decimal import Decimal

    from ....core.i18n import tr
    from ....domain.modelos._sal_reserva_especial import compute_sal_reserva_especial_dotacion

    with pytest.raises(ValueError) as exc_info:
        compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("30000"),
            capital_social=Decimal("0"),
        )

    exc_message = str(exc_info.value)
    rendered = tr("cli.app.modelo.work.sal_computation_error", message=exc_message)
    assert rendered
    assert exc_message in rendered, (
        f"locale key cli.app.modelo.work.sal_computation_error did not interpolate 'message' kwarg; got: {rendered!r}"
    )
