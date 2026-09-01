"""pytest configuration for the cadrumo.core.i18n test scope.

Activates strict-placeholder mode for every test in this package so that
``tr()`` calls with unmatched ``{name}`` tokens raise
:exc:`UnmatchedPlaceholderError` rather than silently returning the
partially-rendered string.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from .render import _I18N_STRICT_MISSING_KEYS, _I18N_STRICT_PLACEHOLDERS


@pytest.fixture(autouse=True)
def _strict_i18n_placeholders() -> Generator[None]:
    """Activate strict-placeholder mode for the duration of each test."""
    token = _I18N_STRICT_PLACEHOLDERS.set(True)
    yield
    _I18N_STRICT_PLACEHOLDERS.reset(token)


@pytest.fixture(autouse=True)
def _strict_i18n_missing_keys() -> Generator[None]:
    """Activate strict-missing-key mode for the duration of each test.

    Scoped to this package rather than the suite: a key the catalogue does
    not carry now raises here, while every other scope keeps the humanised
    fallback until the suite-wide blast radius is measured.
    """
    token = _I18N_STRICT_MISSING_KEYS.set(True)
    yield
    _I18N_STRICT_MISSING_KEYS.reset(token)
