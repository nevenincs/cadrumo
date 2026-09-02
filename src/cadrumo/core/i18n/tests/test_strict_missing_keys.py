"""Strict-missing-key mode: refuse a key no catalogue carries.

Outside strict mode ``tr`` humanises an unknown key into a plausible label, so
a dangling call site renders as ordinary prose and never fails. Strict mode is
the test-scope switch that turns that silence into a refusal.
"""

from __future__ import annotations

import pytest

from ..render import I18N_STRICT_MISSING_KEYS, MissingTranslationError, tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ABSENT_KEY = "zzz.nonexistent.foo_bar"
_TRANSLATED_KEY = "cli.root.verbose_help"


def test_missing_key_refuses_under_strict_mode() -> None:
    """An unknown key raises, carrying the key and locale that failed."""
    with pytest.raises(MissingTranslationError) as excinfo:
        tr(_ABSENT_KEY, locale="en")

    assert excinfo.value.key == _ABSENT_KEY
    assert excinfo.value.locale == "en"


def test_missing_key_error_names_the_remedy() -> None:
    """The refusal tells the operator the catalogue needs a real translation."""
    with pytest.raises(MissingTranslationError) as excinfo:
        tr(_ABSENT_KEY, locale="en")

    message = str(excinfo.value)
    assert _ABSENT_KEY in message
    assert "locale catalogues" in message


def test_explicit_default_opts_into_the_fallback() -> None:
    """A caller supplying ``default`` has chosen a fallback and never raises."""
    assert tr(_ABSENT_KEY, locale="en", default="Fallback label") == "Fallback label"


def test_translated_key_does_not_raise_under_strict_mode() -> None:
    """Anti-vacuity: strict mode refuses unknown keys, not every key."""
    assert tr(_TRANSLATED_KEY, locale="en") == "Enable detailed output."


def test_production_humanises_the_missing_key() -> None:
    """With strict mode off, a missing key still renders — never aborts a filing."""
    token = I18N_STRICT_MISSING_KEYS.set(False)
    try:
        assert tr(_ABSENT_KEY, locale="en") == "Foo bar"
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)
