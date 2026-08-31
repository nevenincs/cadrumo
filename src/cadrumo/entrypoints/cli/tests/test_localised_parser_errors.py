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
