"""Round-trip test for the `year` data_type on `CasillaDefinition`."""

from __future__ import annotations

import pytest

from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `year` data_type tag."""

    def test_year_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("year")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "year"
        assert round_tripped == casilla
