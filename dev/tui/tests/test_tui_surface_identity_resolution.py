"""The executable harness registry must agree with the derived source inventory."""

from __future__ import annotations

import pytest

from .. import _coverage, _harness, _inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _live_registry() -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Read surface names and painted interfaces from the running harness."""
    surfaces = tuple(surface.name for surface in _harness.surfaces())
    return surfaces, _harness.coverage()


def test_the_live_registry_names_only_discovered_interfaces() -> None:
    """A stale class or surface identity is rejected at the real process seam."""
    interfaces = _inventory.scan()
    surfaces, painted = _live_registry()

    assert surfaces, "the harness exposed no executable surfaces"
    assert painted, "the harness exposed no interface coverage"
    _coverage.check(interfaces, surfaces, rendered_table=painted)


def test_every_coverage_row_belongs_to_an_executable_surface() -> None:
    """Scenario rows may share a base identity, but no row may be undrivable."""
    surfaces, painted = _live_registry()

    assert set(painted) <= set(surfaces)
    assert all(qualnames for qualnames in painted.values())


def test_the_live_join_has_detector_teeth_on_both_identities() -> None:
    """A synthetic stale row proves the join, without editing production state."""
    interfaces = _inventory.scan()
    surfaces, painted = _live_registry()
    known_surface = surfaces[0]

    with pytest.raises(_coverage.CoverageError, match="unknown surface"):
        _coverage.check(
            interfaces,
            surfaces,
            rendered_table={**painted, "removed-surface": (interfaces[0].qualname,)},
        )
    with pytest.raises(_coverage.CoverageError, match="unknown interface"):
        _coverage.check(
            interfaces,
            surfaces,
            rendered_table={**painted, known_surface: ("cadrumo.entrypoints.tui.removed.StaleScreen",)},
        )
