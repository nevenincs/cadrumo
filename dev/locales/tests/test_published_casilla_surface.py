"""The published casilla surface is walked once per authority generation and follows a new one."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from dev.locales import casilla_source_inventory
from dev.locales.casilla_source_inventory import published_surface

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_one_generation_is_walked_once_and_served_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(casilla_source_inventory, "surface_by_generation", {})

    first = published_surface()

    assert published_surface() is first
    occurrences, evolutions, binding_keys = first
    assert occurrences, "the published generation declares casillas"
    assert isinstance(evolutions, MappingProxyType)
    assert isinstance(binding_keys, frozenset)


def test_a_surface_remembered_for_another_generation_is_not_served(monkeypatch: pytest.MonkeyPatch) -> None:
    with bundled_indexed_authority().operation() as operation:
        current = operation.generation.logical_generation
    stale = ((), MappingProxyType({}), frozenset({"stale"}))
    monkeypatch.setattr(casilla_source_inventory, "surface_by_generation", {f"not-{current}": stale})

    occurrences, _evolutions, binding_keys = published_surface()

    assert occurrences, "a different generation's surface must be re-walked, not reused"
    assert "stale" not in binding_keys
    assert set(casilla_source_inventory.surface_by_generation) == {current}
