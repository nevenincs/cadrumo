"""Fail-closed compatibility surface for the retired ruleset registry."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import RegistrySnapshotError


@dataclass(frozen=True, slots=True)
class CalculationCatalogueTarget:
    """Retired catalogue target shape retained for import compatibility."""

    modelo: str
    period: str
    fiscal_period: str
    variant: str = "default"


class CalculationRegistry:
    """Retired ruleset registry facade.

    Filing-grade calculation now flows through validated
    :class:`aeat.domain.calculations.registry.RegistrySnapshot` objects.
    This facade exists only to fail closed if an old caller is still present.
    """

    def metadata_for(self, modelo: object) -> object:
        """Reject legacy metadata resolution."""
        _ = modelo
        raise RegistrySnapshotError("legacy calculation registry is disabled; use registry snapshots")

    def resolve_ruleset(self, **kwargs: object) -> object:
        """Reject legacy ruleset resolution."""
        _ = kwargs
        raise RegistrySnapshotError("legacy calculation rulesets are disabled; use registry snapshots")

    def catalogue_targets(self, **kwargs: object) -> tuple[CalculationCatalogueTarget, ...]:
        """Reject legacy catalogue target materialization."""
        _ = kwargs
        raise RegistrySnapshotError("legacy calculation catalogue targets are disabled; use registry snapshots")


def get_calculation_registry() -> CalculationRegistry:
    """Reject access to the retired ruleset-backed registry."""
    raise RegistrySnapshotError("legacy calculation registry is disabled; use registry snapshots")


__all__ = [
    "CalculationCatalogueTarget",
    "CalculationRegistry",
    "get_calculation_registry",
]
