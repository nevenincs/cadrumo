"""Handshakes state the installed version without scanning distribution metadata again."""

from __future__ import annotations

import sys
from collections.abc import Callable
from importlib.metadata import version

import pytest

from ..product_version import installed_product_version

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# Distribution discovery lists every import path entry and opens archives and metadata files.
_SCAN_EVENTS = frozenset({"os.listdir", "os.scandir", "open"})
_observed_events: list[str] | None = None


def _record_scan_event(event: str, _arguments: tuple[object, ...]) -> None:
    if _observed_events is not None and event in _SCAN_EVENTS:
        _observed_events.append(event)


sys.addaudithook(_record_scan_event)


def _scan_events_during(action: Callable[[], object]) -> list[str]:
    global _observed_events
    _observed_events = []
    try:
        action()
        return _observed_events
    finally:
        _observed_events = None


def test_handshakes_after_the_first_read_scan_no_distribution_metadata() -> None:
    installed_product_version.cache_clear()
    first = _scan_events_during(installed_product_version)
    # The first read is a real metadata scan, which the audit hook observes.
    assert first
    handshakes = _scan_events_during(lambda: [installed_product_version(), installed_product_version()])
    assert handshakes == []
    assert installed_product_version() == version("cadrumo")
