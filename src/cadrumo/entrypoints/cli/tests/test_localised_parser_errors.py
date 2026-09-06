"""Localised refusal-payload tests for the shared amount / date parsers.

Drives the real :func:`parse_decimal_amount` and :func:`_parse_iso_date`
helpers in :mod:`cadrumo.entrypoints.cli._common` once under each of the four
target locales (``en``, ``es``, ``ca``, ``hu``) and asserts the rendered
refusal payload carries the field label, the raw operator value, and — for the
decimal refusal — the expected-format hint, in every locale.

A refusal must name the field, echo what the operator typed, and state the
accepted form in all four locales — never a bare "invalid" that varies by
language. No mocks, no skips: the real catalogue and the real parse path are
exercised end to end.
"""

from __future__ import annotations

from typing import cast

from .._terminal_errors import _render_click_exception_text

from collections.abc import Iterator

import pytest
import typer

from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import clear_output_language_cache
from .._date_parsing import _parse_iso_date
from .._decimal_parsing import parse_decimal_amount

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = (OutputLanguage.EN, OutputLanguage.ES, OutputLanguage.CA, OutputLanguage.HU)

# The expected-format hint example the decimal refusal must surface in every
# locale (the canonical accepted shape: dot decimal, no thousands grouping).
_EXPECTED_FORMAT_HINT = "1234.56"


def _render_decimal_refusal(locale: OutputLanguage, raw: str) -> str:
    with override_settings(cadrumo_output_language=locale.value):
        clear_output_language_cache()
        with pytest.raises(typer.BadParameter) as excinfo:
            parse_decimal_amount(raw, label="taxable-base", signed=False)
        return excinfo.value.message


def _render_date_refusal(locale: OutputLanguage, raw: str) -> str:
    with override_settings(cadrumo_output_language=locale.value):
        clear_output_language_cache()
        with pytest.raises(typer.BadParameter) as excinfo:
            _parse_iso_date(raw, label="invoice-date")
        return excinfo.value.message


@pytest.fixture(autouse=True)
def _reset_locale_cache() -> Iterator[None]:
    yield
    clear_output_language_cache()


def test_decimal_refusal_carries_label_raw_and_hint_in_every_locale() -> None:
    for locale in _LOCALES:
        message = _render_decimal_refusal(locale, "1.000")
        assert "taxable-base" in message, f"{locale.value}: label missing -> {message!r}"
        assert "1.000" in message, f"{locale.value}: raw value missing -> {message!r}"
        assert _EXPECTED_FORMAT_HINT in message, f"{locale.value}: format hint missing -> {message!r}"


def test_date_refusal_carries_label_and_raw_in_every_locale() -> None:
    for locale in _LOCALES:
        message = _render_date_refusal(locale, "15/01/2026")
        assert "invoice-date" in message, f"{locale.value}: label missing -> {message!r}"
        assert "15/01/2026" in message, f"{locale.value}: raw value missing -> {message!r}"


def test_decimal_refusal_text_differs_across_locales() -> None:
    # Anti-tautology guard: the four messages must be genuinely translated, not
    # the same English string echoed under four locale codes.
    rendered = {locale.value: _render_decimal_refusal(locale, "1.000") for locale in _LOCALES}
    assert len({rendered["en"], rendered["es"], rendered["ca"], rendered["hu"]}) == 4, rendered


def test_date_refusal_text_differs_across_locales() -> None:
    rendered = {locale.value: _render_date_refusal(locale, "15/01/2026") for locale in _LOCALES}
    assert len({rendered["en"], rendered["es"], rendered["ca"], rendered["hu"]}) == 4, rendered


def test_the_click_exception_funnel_calls_the_renderer_rather_than_writing_the_bare_message() -> None:
    """The plain-text funnel must reach the exception's own renderer.

    `_render_click_exception_text` read `getattr(exc, "view", None)`. No click
    exception has a `view`, so the lookup always failed and every parse refusal
    fell through to a bare `str(exc)` write -- losing the `Error:` prefix, the
    usage block, the "Try ... for help" hint, and the parameter name. An
    operator saw a value rejected with no statement of WHICH option rejected
    it, and the localised `UsageError.show` reimplementation this project
    installs was dead code in the text path.

    The failure was silent by construction: `getattr` with a default returns
    None rather than raising, and the fallback prints something plausible. So
    this asserts the funnel drives the real method, by giving it an exception
    whose renderer records that it ran.
    """

    class _Recording:
        """A click-exception stand-in that records whether its renderer ran."""

        def __init__(self) -> None:
            self.rendered = False

        def show(self) -> None:
            self.rendered = True

        def __str__(self) -> str:
            return "bare message"

    exception = _Recording()

    _render_click_exception_text(cast("BaseException", exception))

    assert exception.rendered, (
        "the funnel wrote the bare message instead of calling the exception's renderer, so "
        "every parse refusal loses its prefix, usage block, hint, and parameter name"
    )
