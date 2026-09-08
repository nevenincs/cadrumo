"""Gate: every declared fixture registry must be reachable from ``SURFACES``.

A fixture registry that nothing registers is invisible in the only way that
matters: the harness cannot render it, so the states it declares are never
looked at, and the fixtures rot against the screens they were written for.

The failure this was built from is exactly that. ``modelo_fixtures`` declared
eleven Modelo workspace, review and edit states with the same spec shape
``workbench_fixtures`` uses, and both modules' docstrings anticipated "the
later central-registry merge" -- but ``SURFACES`` spread only the workbench
registry, so the Modelo half had never been drivable. Nothing was red: the
module imports, its own tests pass, and the harness listed 87 surfaces
without any indication that eleven more existed.

The check is on identity, not count, so adding a fixture to a registered
registry needs no edit here, and adding a whole new registry fails until it
is spread into ``SURFACES``.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Final

import pytest

from .. import surfaces as surfaces_module
from ..surfaces import SURFACES

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The suffix a fixture registry's module-level spec tuple carries.
_REGISTRY_SUFFIX: Final = "_FIXTURES"


def declared_registries() -> dict[str, tuple[Any, ...]]:
    """Return every ``*_FIXTURES`` spec tuple the harness package declares.

    Discovered rather than listed. A hand-maintained inventory here would have
    the same defect as the one it checks for -- a new registry would be absent
    from both the inventory and ``SURFACES``, and the gate would pass.
    """
    package = importlib.import_module("dev.tui.harness")
    found: dict[str, tuple[Any, ...]] = {}
    for info in pkgutil.iter_modules(package.__path__):
        if info.name == "tests":
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        for name, value in vars(module).items():
            if name.endswith(_REGISTRY_SUFFIX) and isinstance(value, tuple) and value:
                found[f"{info.name}.{name}"] = value
    return found


def unregistered_fixture_ids(
    registries: dict[str, tuple[Any, ...]],
    registered: frozenset[str],
) -> list[str]:
    """Return ``registry -> fixture_id`` for every spec no surface exposes."""
    return [
        f"{registry} -> {spec.fixture_id}"
        for registry, specs in sorted(registries.items())
        for spec in specs
        if getattr(spec, "fixture_id", None) is not None and spec.fixture_id not in registered
    ]


def test_the_package_still_declares_fixture_registries() -> None:
    """A population floor: discovering nothing would make the check vacuous."""
    registries = declared_registries()

    assert len(registries) >= 2, (
        f"found only {len(registries)} fixture registry/registries in the harness "
        "package; the discovery has drifted and the gate is inert rather than satisfied"
    )


def test_every_declared_fixture_is_a_drivable_surface() -> None:
    """The direction the gate exists for."""
    missing = unregistered_fixture_ids(declared_registries(), frozenset(SURFACES))

    assert missing == [], (
        "these fixtures are declared but no SURFACES entry exposes them, so the "
        "harness cannot render the states they describe; spread their registry "
        f"into SURFACES rather than deleting them: {missing}"
    )


def test_the_gate_catches_a_registry_no_surface_exposes() -> None:
    """Detector teeth: the exact state ``modelo_fixtures`` was in."""

    class _Spec:
        fixture_id = "modelo-edit--ready"

    missing = unregistered_fixture_ids({"modelo_fixtures.MODELO_FIXTURES": (_Spec(),)}, frozenset())

    assert missing == ["modelo_fixtures.MODELO_FIXTURES -> modelo-edit--ready"]


def test_a_registered_fixture_is_accepted() -> None:
    """The normal case, so the gate is not merely always-red."""

    class _Spec:
        fixture_id = "already-there"

    assert unregistered_fixture_ids({"r.R_FIXTURES": (_Spec(),)}, frozenset({"already-there"})) == []


def test_the_modelo_registry_is_among_the_surfaces() -> None:
    """The specific wiring, named, so a silent unspreading is caught by identity."""
    from ..modelo_fixtures import MODELO_FIXTURES

    assert {spec.fixture_id for spec in MODELO_FIXTURES} <= set(SURFACES)
    assert surfaces_module._modelo_surfaces()
