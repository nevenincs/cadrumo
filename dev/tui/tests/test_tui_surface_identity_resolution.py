"""The executable harness registry must agree with the derived source inventory."""

from __future__ import annotations

import pytest

from .. import coverage, harness_support, inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _live_registry() -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Read surface names -- scenario pages included -- and painted interfaces from the running harness."""
    surfaces = harness_support.reviewable_surface_names(harness_support.surfaces(), harness_support.scenarios())
    return surfaces, harness_support.coverage()


def test_the_live_registry_names_only_discovered_interfaces() -> None:
    """A stale class or surface identity is rejected at the real process seam."""
    interfaces = inventory.scan()
    surfaces, painted = _live_registry()

    assert surfaces, "the harness exposed no executable surfaces"
    assert painted, "the harness exposed no interface coverage"
    coverage.check(interfaces, surfaces, rendered_table=painted)


def test_every_coverage_row_belongs_to_an_executable_surface() -> None:
    """Scenario rows may share a base identity, but no row may be undrivable."""
    surfaces, painted = _live_registry()

    assert set(painted) <= set(surfaces)
    assert all(qualnames for qualnames in painted.values())


def test_the_live_join_has_detector_teeth_on_both_identities() -> None:
    """A synthetic stale row proves the join, without editing production state."""
    interfaces = inventory.scan()
    surfaces, painted = _live_registry()
    known_surface = surfaces[0]

    with pytest.raises(coverage.CoverageError, match="unknown surface"):
        coverage.check(
            interfaces,
            surfaces,
            rendered_table={**painted, "removed-surface": (interfaces[0].qualname,)},
        )
    with pytest.raises(coverage.CoverageError, match="unknown interface"):
        coverage.check(
            interfaces,
            surfaces,
            rendered_table={**painted, known_surface: ("cadrumo.entrypoints.tui.removed.StaleScreen",)},
        )
