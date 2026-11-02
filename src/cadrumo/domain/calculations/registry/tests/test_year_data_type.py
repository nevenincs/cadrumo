"""Roundtrip tests for the `year` data_type and `ModeloYear` alias.

The `year` variant on `CasillaDefinition.data_type` plus the
`ModeloYear` `Annotated` alias on the schema module carry the
registry's fiscal-year contract. These tests exercise the alias
against years written with four digits, the boundary cases at
1000 and 9999, and rejection paths for years of another width, blank,
non-integer, boolean, and float inputs. Which years the registry covers is
not this alias's claim.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors import RegistryValidationError
from ..schema_scalars import ModeloYear, _coerce_modelo_year
from ..schema_surfaces import CasillaDefinition

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
            (1000, 1000),
            (2000, 2000),
            (2025, 2025),
            (2099, 2099),
            (9999, 9999),
            ("2024", 2024),
            ("  2026  ", 2026),
        )

        for raw, canonical in cases:
            assert _YEAR_ADAPTER.validate_python(raw) == canonical, raw


class TestModeloYearRejects:
    """`ModeloYear` rejects out-of-range, malformed, and wrong-type inputs."""

    def test_invalid_values_rejected(self) -> None:
        cases: tuple[object, ...] = (
            999,
            10000,
            "999",
            "10000",
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
        # The validator sits behind the Pydantic translation boundary; the
        # registered refusal is the cause of the ValueError Pydantic reads.
        for raw in ("", True):
            with pytest.raises(ValueError) as refusal:
                _coerce_modelo_year(raw)
            assert isinstance(refusal.value.__cause__, RegistryValidationError)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `year` data_type tag."""

    def test_year_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("year")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "year"
        assert round_tripped == casilla
