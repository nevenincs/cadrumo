"""A source declared over alternative cadences folds the one cadence actually filed."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.aggregation import RelationAggregationOp
from .....core.casilla_id import validated_casilla_id
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..errors import RegistryValidationError
from ..observation_fold import resolve_observed_requirement_value
from ..relations import RegistryFoldRequirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "rd-439-2007:art-108"
_SOURCE_REF = "aeat-modelo-111-instructions"
_TOTAL_RETENCIONES = validated_casilla_id("28", surface="test modelo 111 total retenciones")
_QUARTERS = ("1T", "2T", "3T", "4T")
_MONTHS = tuple(f"{month:02d}" for month in range(1, 13))


def _requirement(periods: tuple[str, ...]) -> RegistryFoldRequirement:
    return RegistryFoldRequirement(
        source_modelo="111",
        filing_year=2025,
        periods=periods,
        source_casilla_ids=(_TOTAL_RETENCIONES,),
        target_bindings=("renta-modelo-111-retenciones-periodicas",),
        aggregation_op=RelationAggregationOp.SUM,
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


def _filing(period: str, value: str) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="111",
        filing_year=2025,
        period=period,
        observations=(
            CasillaObservation(
                casilla_id=_TOTAL_RETENCIONES,
                value=Decimal(value),
                legal_refs=(_LEGAL_REF,),
                source_refs=(_SOURCE_REF,),
            ),
        ),
    )


def test_a_quarterly_filer_folds_its_four_quarters() -> None:
    filings = tuple(_filing(period, value) for period, value in zip(_QUARTERS, ("10", "20", "30", "40"), strict=True))

    assert resolve_observed_requirement_value(_requirement(_QUARTERS + _MONTHS), filings) == Decimal("100")


def test_a_monthly_filer_folds_its_twelve_months() -> None:
    filings = tuple(_filing(month, "5") for month in _MONTHS)

    assert resolve_observed_requirement_value(_requirement(_QUARTERS + _MONTHS), filings) == Decimal("60")


def test_an_incomplete_cadence_is_not_folded() -> None:
    filings = tuple(_filing(period, "10") for period in _QUARTERS[:3])

    with pytest.raises(RegistryValidationError, match="exactly one completely filed cadence"):
        resolve_observed_requirement_value(_requirement(_QUARTERS + _MONTHS), filings)


def test_two_complete_cadences_are_ambiguous_and_refused() -> None:
    filings = tuple(_filing(period, "10") for period in _QUARTERS) + tuple(_filing(month, "5") for month in _MONTHS)

    with pytest.raises(RegistryValidationError, match="found 2"):
        resolve_observed_requirement_value(_requirement(_QUARTERS + _MONTHS), filings)


def test_a_single_cadence_declaration_still_requires_every_period() -> None:
    filings = tuple(_filing(period, "10") for period in _QUARTERS[:3])

    with pytest.raises(RegistryValidationError, match="expected one observed filing"):
        resolve_observed_requirement_value(_requirement(_QUARTERS), filings)
