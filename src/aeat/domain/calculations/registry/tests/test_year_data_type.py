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

from .._errors import RegistryValidationError
from .._schema import CasillaDefinition, ModeloYear, _coerce_modelo_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_YEAR_ADAPTER: TypeAdapter[int] = TypeAdapter(ModeloYear)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "year_test_casilla",
            "number": "01",
            "label": "Ejercicio",
            "section": ("declarante",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


class TestModeloYearAccepts:
    """`ModeloYear` accepts integers and digit strings within the window."""

    @pytest.mark.parametrize(
        "raw,canonical",
        [
            (2000, 2000),
            (2025, 2025),
            (2099, 2099),
            ("2024", 2024),
            ("  2026  ", 2026),
        ],
    )
    def test_canonical_input_returns_int(self, raw: object, canonical: int) -> None:
        assert _YEAR_ADAPTER.validate_python(raw) == canonical


class TestModeloYearRejects:
    """`ModeloYear` rejects out-of-range, malformed, and wrong-type inputs."""

    @pytest.mark.parametrize("raw", [1999, 2100, "1999", "2100"])
    def test_out_of_range_rejected(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            _YEAR_ADAPTER.validate_python(raw)

    @pytest.mark.parametrize("raw", ["", "   ", "twenty-twenty", "20.25"])
    def test_non_integer_string_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _YEAR_ADAPTER.validate_python(raw)

    def test_boolean_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _YEAR_ADAPTER.validate_python(True)

    def test_float_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _YEAR_ADAPTER.validate_python(2024.5)

    def test_blank_string_raises_registry_validation_error_at_validator(self) -> None:
        with pytest.raises(RegistryValidationError):
            _coerce_modelo_year("")

    def test_boolean_raises_registry_validation_error_at_validator(self) -> None:
        with pytest.raises(RegistryValidationError):
            _coerce_modelo_year(True)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `year` data_type tag."""

    def test_year_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("year")
        round_tripped = CasillaDefinition.model_validate(casilla.model_dump())
        assert round_tripped.data_type == "year"
        assert round_tripped == casilla
