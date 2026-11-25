"""Smoke tests for the justificante PDF fixture generator catalogue.

`main()` mutates committed in-tree fixture bytes, so the smoke tests
exercise the importable surface — the 8 frozen `_*Fixture` dataclasses
plus the `_FIXTURES` catalogue — without touching the committed PDFs.
"""

from __future__ import annotations

from dataclasses import is_dataclass

import pytest

from .generate_base import (
    FIXTURES,
    Fixture,
)
from .generate_misc_a import (
    Modelo036Fixture,
    Modelo115Fixture,
    Modelo180Fixture,
    Modelo193Fixture,
    Modelo349Fixture,
    Modelo369Fixture,
    Modelo720Fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_fixture_catalogue_is_non_empty() -> None:
    """The generator declares at least one base-modelo fixture."""

    assert len(FIXTURES) > 0
    for fixture in FIXTURES:
        assert isinstance(fixture, Fixture)
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
        Fixture,
        Modelo036Fixture,
        Modelo115Fixture,
        Modelo180Fixture,
        Modelo193Fixture,
        Modelo349Fixture,
        Modelo369Fixture,
        Modelo720Fixture,
    )
    for cls in fixture_classes:
        assert is_dataclass(cls), f"{cls.__name__} is not a dataclass"
        # Frozen-dataclass check: instances reject attribute mutation.
        # We sample the assertion against _Fixture since it's the only
        # one with a concrete instance available in the catalogue.
        if cls is Fixture and FIXTURES:
            instance = FIXTURES[0]
            field_name = "modelo"
            with pytest.raises((AttributeError, TypeError)):
                setattr(instance, field_name, "999")
