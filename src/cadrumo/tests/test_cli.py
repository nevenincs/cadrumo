"""Behavior contract for the ``core.i18n`` default output language."""

from __future__ import annotations

import pytest

from ..core.i18n import DEFAULT_OUTPUT_LANGUAGE

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_default_output_language_constant_is_es() -> None:
    """DEFAULT_OUTPUT_LANGUAGE equals 'es' (behavior contract — constant introduction).

    The constant was introduced as the canonical spelling of the Spanish
    fallback. Every 'es' fallback in _render.py now references this
    constant; this test locks its value so accidental changes fail loudly.
    """
    assert DEFAULT_OUTPUT_LANGUAGE == "es"
