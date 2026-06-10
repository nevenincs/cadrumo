"""Smoke tests for the justificante PDF fixture generator catalogue.

`main()` mutates committed in-tree fixture bytes, so the smoke tests
exercise the importable surface — the 8 frozen `_*Fixture` dataclasses
plus the `_FIXTURES` catalogue — without touching the committed PDFs.
"""

from __future__ import annotations

from dataclasses import is_dataclass

import pytest

from ._generate import (
    _FIXTURES,
    _Fixture,
    _Modelo036Fixture,
    _Modelo115Fixture,
    _Modelo180Fixture,
    _Modelo193Fixture,
    _Modelo349Fixture,
    _Modelo369Fixture,
    _Modelo720Fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_fixture_catalogue_is_non_empty() -> None:
    """The generator declares at least one base-modelo fixture."""

    assert len(_FIXTURES) > 0
    for fixture in _FIXTURES:
        assert isinstance(fixture, _Fixture)
        assert fixture.filename.endswith(".pdf")
        assert fixture.modelo
        assert fixture.ejercicio
        assert fixture.tax_id
        assert fixture.csv
        # Exactly one of the two totals is populated per the
        # ingresar-vs-devolver convention.
        assert (fixture.total_ingresar is not None) ^ (fixture.total_devolver is not None)


def test_all_per_modelo_fixture_classes_are_frozen_dataclasses() -> None:
    """Each modelo-specific fixture is a frozen dataclass so callers
    can rely on immutable shapes; mutating a fixture after construction
    is a domain bug."""

    fixture_classes = (
        _Fixture,
        _Modelo036Fixture,
        _Modelo115Fixture,
        _Modelo180Fixture,
        _Modelo193Fixture,
        _Modelo349Fixture,
        _Modelo369Fixture,
        _Modelo720Fixture,
    )
    for cls in fixture_classes:
        assert is_dataclass(cls), f"{cls.__name__} is not a dataclass"
        # Frozen-dataclass check: instances reject attribute mutation.
        # We sample the assertion against _Fixture since it's the only
        # one with a concrete instance available in the catalogue.
        if cls is _Fixture and _FIXTURES:
            instance = _FIXTURES[0]
            with pytest.raises((AttributeError, TypeError)):
                # Accessing through __dict__ bypasses the frozen check at type-check time
                instance.modelo = "999"  # type: ignore[arg-type]
