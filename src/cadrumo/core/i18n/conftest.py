"""pytest configuration for the aeat.core.i18n test scope.

Activates strict-placeholder mode for every test in this package so that
``tr()`` calls with unmatched ``{name}`` tokens raise
:exc:`UnmatchedPlaceholderError` rather than silently returning the
partially-rendered string.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from ._render import _I18N_STRICT_PLACEHOLDERS


@pytest.fixture(autouse=True)
def _strict_i18n_placeholders() -> Generator[None]:
    """Activate strict-placeholder mode for the duration of each test."""
    token = _I18N_STRICT_PLACEHOLDERS.set(True)
    yield
    _I18N_STRICT_PLACEHOLDERS.reset(token)
