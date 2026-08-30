"""Real-behavior contract tests for browser timeout constants."""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RENTA_MODULE = "cadrumo.adapters.outbound.aeat.sede.renta_web_open"


def test_visible_probe_timeout_constant_value() -> None:
    """``_VISIBLE_PROBE_TIMEOUT_MS`` equals 2 000 ms (short fast-path probe)."""

    mod = importlib.import_module(_RENTA_MODULE)

    assert mod._VISIBLE_PROBE_TIMEOUT_MS == 2_000


def test_element_wait_timeout_constant_value() -> None:
    """``_ELEMENT_WAIT_TIMEOUT_MS`` equals 10 000 ms (standard form-interaction budget)."""

    mod = importlib.import_module(_RENTA_MODULE)

    assert mod._ELEMENT_WAIT_TIMEOUT_MS == 10_000
