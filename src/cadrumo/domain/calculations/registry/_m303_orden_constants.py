"""Shared shape constants and coordinate validation for annual Orden authority."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .errors import RegistryValidationError
from .ids import RevisionId, SourceRefId

EXPECTED_ACTIVITY_COUNT = 49
EXPECTED_MODULE_COUNT = 141
EXPECTED_MODULE_DISTRIBUTION = {1: 2, 2: 25, 3: 12, 4: 4, 5: 1, 6: 3, 7: 2}
EXPECTED_MODULE_DISTRIBUTION_VECTOR = (2, 25, 12, 4, 1, 3, 2)
EXPECTED_NON_AGRICULTURAL_INGRESO_A_CUENTA_COUNT = 47
EXPECTED_AGRICULTURAL_AXIS_COUNTS = {2022: 16, 2023: 16, 2024: 16, 2025: 17, 2026: 17}
#: Shape bounds for the temporada corrector bands, NOT their values. The
#: coefficients and day bands are fixed by each annual Orden and are already
#: grounded in the census by its own required_text; asserting them here would
#: make a lawful change to a coefficient indistinguishable from a corrupt
#: extraction, and the validator would refuse the new law. What is safe to
#: assert is that the bands remain a contiguous ascending partition carrying
#: positive coefficients, which a garbled extraction would violate.
MINIMUM_SEASONAL_INDEX_BANDS = 1
FIRST_SEASONAL_INDEX_DAY = 1
EXTRACTOR_VERSION = "m303-annual-orden-html-v5"


class _GeneratedSourceShape(Protocol):
    ejercicio: int
    activity_table_count: int
    module_row_count: int
    module_distribution: tuple[int, ...]
    agricultural_index_row_count: int
    agricultural_ingreso_a_cuenta_row_count: int
    non_agricultural_ingreso_a_cuenta_row_count: int
    seasonal_index_day_bands: tuple[tuple[int, int], ...]
    seasonal_index_coefficients: tuple[Decimal, ...]
    difficult_justification_pct: Decimal
    lorca_2022_reduction_pct: Decimal | None


def _validate_generated_source_counts(source: _GeneratedSourceShape) -> None:
    expected_agricultural_count = EXPECTED_AGRICULTURAL_AXIS_COUNTS.get(source.ejercicio)
    if source.activity_table_count != EXPECTED_ACTIVITY_COUNT:
        raise RegistryValidationError("annual Orden manifest has the wrong activity table count")
    if source.module_row_count != EXPECTED_MODULE_COUNT:
        raise RegistryValidationError("annual Orden manifest has the wrong module row count")
    if source.module_distribution != EXPECTED_MODULE_DISTRIBUTION_VECTOR:
        raise RegistryValidationError("annual Orden manifest has the wrong module distribution")
    if (
        expected_agricultural_count is None
        or source.agricultural_index_row_count != expected_agricultural_count
        or source.agricultural_ingreso_a_cuenta_row_count != expected_agricultural_count
    ):
        raise RegistryValidationError("annual Orden manifest has the wrong agricultural axis row count")


def _validate_generated_source_axis_shape(source: _GeneratedSourceShape) -> None:
    if source.non_agricultural_ingreso_a_cuenta_row_count != EXPECTED_NON_AGRICULTURAL_INGRESO_A_CUENTA_COUNT:
        raise RegistryValidationError("annual Orden manifest has the wrong IAE ingreso-a-cuenta row count")
    validate_seasonal_index_shape(
        source.seasonal_index_day_bands,
        source.seasonal_index_coefficients,
        scope="manifest",
    )
    validate_percentage_shape(
        source.difficult_justification_pct,
        scope="manifest",
        subject="difficult-justification",
    )
    if source.ejercicio == 2022:
        if source.lorca_2022_reduction_pct is None:
            raise RegistryValidationError("annual Orden 2022 manifest lacks its Lorca reduction percentage")
        validate_percentage_shape(source.lorca_2022_reduction_pct, scope="manifest", subject="Lorca 2022 reduction")
    elif source.lorca_2022_reduction_pct is not None:
        raise RegistryValidationError("only the 2022 annual Orden manifest may state the Lorca reduction")


def validate_seasonal_index_shape(
    day_bands: tuple[tuple[int, int], ...],
    coefficients: tuple[Decimal, ...],
    *,
    scope: str,
) -> None:
    """Refuse a temporada corrector table that is structurally impossible.

    Asserts SHAPE, never the legal figures: the bands must be a contiguous
    ascending partition starting at day one, each band non-empty, with one
    positive coefficient apiece. A future Orden may change any coefficient or
    band boundary and still satisfy this; a garbled extraction cannot.

    Raises:
        RegistryValidationError: If the table is empty, misaligned, or carries a
            non-positive coefficient.
    """
    if len(day_bands) < MINIMUM_SEASONAL_INDEX_BANDS:
        raise RegistryValidationError(f"annual Orden {scope} declares no seasonal index band")
    if len(day_bands) != len(coefficients):
        raise RegistryValidationError(f"annual Orden {scope} seasonal bands and coefficients disagree in length")
    expected_start = FIRST_SEASONAL_INDEX_DAY
    for start, end in day_bands:
        if start != expected_start:
            raise RegistryValidationError(f"annual Orden {scope} seasonal index bands are not contiguous")
        if end < start:
            raise RegistryValidationError(f"annual Orden {scope} seasonal index band ends before it starts")
        expected_start = end + 1
    if any(coefficient <= 0 for coefficient in coefficients):
        raise RegistryValidationError(f"annual Orden {scope} seasonal index coefficient is not positive")


def validate_percentage_shape(percentage: Decimal, *, scope: str, subject: str) -> None:
    """Refuse a percentage outside the only range a percentage can occupy.

    Asserts SHAPE, never the legal figure, for the same reason as
    :func:`validate_seasonal_index_shape`.

    Raises:
        RegistryValidationError: If ``percentage`` is negative or above 100.
    """
    if percentage < 0 or percentage > 100:
        raise RegistryValidationError(f"annual Orden {scope} {subject} percentage is outside 0-100")


validate_generated_source_counts = _validate_generated_source_counts
validate_generated_source_axis_shape = _validate_generated_source_axis_shape

_M303_2022_REVISION_ID = "2022"
_M303_2022_ORDEN_SOURCE_REF = "boe-orden-hfp-1335-2021-iva-authority"
_M303_2022_ORDEN_SOURCE_DIGEST = "3fda96dcf2dcb3b3f0863bc07b0eabd45e21c6850d4b611e635627befb450c46"


def _validate_2022_annual_orden_coordinate(
    *,
    ejercicio: int,
    registry_revision_id: RevisionId,
    source_ref: SourceRefId,
    source_content_digest: str,
    scope: str,
) -> None:
    """Require the pinned BOE/revision coordinate for 2022 annual authority."""
    if not (
        ejercicio == 2022
        and registry_revision_id == _M303_2022_REVISION_ID
        and source_ref == _M303_2022_ORDEN_SOURCE_REF
        and source_content_digest == _M303_2022_ORDEN_SOURCE_DIGEST
    ):
        raise RegistryValidationError(f"annual Orden 2022 {scope} must retain its exact BOE/revision coordinate")


validate_2022_annual_orden_coordinate = _validate_2022_annual_orden_coordinate
