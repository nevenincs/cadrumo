"""Tests for the retired legacy calculation registry facade."""

from __future__ import annotations

import pytest

from ._registry import CalculationRegistry, get_calculation_registry
from .registry import RegistrySnapshotError

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_get_calculation_registry_requires_registry_snapshots() -> None:
    with pytest.raises(RegistrySnapshotError, match="legacy calculation registry is disabled"):
        get_calculation_registry()


def test_resolve_ruleset_requires_registry_snapshots() -> None:
    registry = CalculationRegistry()

    with pytest.raises(RegistrySnapshotError, match="legacy calculation rulesets are disabled"):
        registry.resolve_ruleset(modelo="130", period="2025Q1")


def test_catalogue_targets_require_registry_snapshots() -> None:
    registry = CalculationRegistry()

    with pytest.raises(RegistrySnapshotError, match="legacy calculation catalogue targets are disabled"):
        registry.catalogue_targets(modelo="130", year=2025)
