"""Roundtrip tests for the `year` data_type and `ModeloYear` alias.

The `year` variant on `CasillaDefinition.data_type` plus the
`ModeloYear` `Annotated` alias on the schema module carry the
registry's fiscal-year contract. These tests exercise the alias
against valid years in the supported window, the boundary cases at
2000 and 2099, and rejection paths for out-of-range, blank,
non-integer, boolean, and float inputs. The window matches
`RegistrySnapshotRef.modelo_year`.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.domain.calculations.registry.schema import ModeloYear, _coerce_modelo_year
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_YEAR_ADAPTER: TypeAdapter[int] = TypeAdapter(ModeloYear)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "year_test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("declarante",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


class TestModeloYearAccepts:
    """`ModeloYear` accepts integers and digit strings within the window."""

    def test_canonical_input_returns_int(self) -> None:
        cases = (
            (2000, 2000),
            (2025, 2025),
            (2099, 2099),
            ("2024", 2024),
            ("  2026  ", 2026),
        )

        for raw, canonical in cases:
            assert _YEAR_ADAPTER.validate_python(raw) == canonical, raw


class TestModeloYearRejects:
    """`ModeloYear` rejects out-of-range, malformed, and wrong-type inputs."""

    def test_invalid_values_rejected(self) -> None:
        cases: tuple[object, ...] = (
            1999,
            2100,
            "1999",
            "2100",
            "",
            "   ",
            "twenty-twenty",
            "20.25",
            True,
            2024.5,
        )

        for raw in cases:
            with pytest.raises(ValidationError):
                _YEAR_ADAPTER.validate_python(raw)

    def test_invalid_value_raises_registry_validation_error_at_validator(self) -> None:
        for raw in ("", True):
            with pytest.raises(RegistryValidationError):
                _coerce_modelo_year(raw)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `year` data_type tag."""

    def test_year_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("year")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "year"
        assert round_tripped == casilla
