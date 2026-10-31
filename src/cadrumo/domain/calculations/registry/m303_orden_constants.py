"""Shared shape constants and coordinate validation for annual Orden authority."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from .errors import RegistryValidationError
from .ids import SourceRefId

#: Shape bounds for the temporada corrector bands, NOT their values. The
#: coefficients and day bands are fixed by each annual Orden and are already
#: grounded in the census by its own required_text; asserting them here would
#: make a lawful change to a coefficient indistinguishable from a corrupt
#: extraction, and the validator would refuse the new law. What is safe to
#: assert is that the bands remain a contiguous ascending partition carrying
#: positive coefficients, which a garbled extraction would violate.
MINIMUM_SEASONAL_INDEX_BANDS = 1
FIRST_SEASONAL_INDEX_DAY = 1
EXTRACTOR_VERSION = "m303-annual-orden-html-v7"


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
    lorca_reduction_pct: Decimal | None


def validate_generated_source_counts(source: _GeneratedSourceShape) -> None:
    """Refuse manifest counts that contradict one another.

    Each annual Orden states its own table sizes, so the manifest row holds them
    and is compared to a fresh extraction of the pinned BOE source. This check
    asserts only what must hold in any year: the distribution adds up to the
    tables and rows it describes, and both agricultural axes list the same rows.
    """
    if source.activity_table_count != sum(source.module_distribution):
        raise RegistryValidationError("annual Orden manifest activity count disagrees with its module distribution")
    if source.module_row_count != sum(
        size * occurrences for size, occurrences in enumerate(source.module_distribution, start=1)
    ):
        raise RegistryValidationError("annual Orden manifest module count disagrees with its module distribution")
    if source.agricultural_index_row_count != source.agricultural_ingreso_a_cuenta_row_count:
        raise RegistryValidationError("annual Orden manifest agricultural axes disagree in row count")


def validate_generated_source_axis_shape(source: _GeneratedSourceShape) -> None:
    """Validate that generated M303 source axes have the required shape."""
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
    if source.lorca_reduction_pct is not None:
        validate_percentage_shape(source.lorca_reduction_pct, scope="manifest", subject="Lorca reduction")


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


_M303_2022_ORDEN_SOURCE_REF = "boe-orden-hfp-1335-2021-iva-authority"
_M303_2022_ORDEN_SOURCE_DIGEST = "3fda96dcf2dcb3b3f0863bc07b0eabd45e21c6850d4b611e635627befb450c46"


def validate_2022_annual_orden_coordinate(
    *,
    ejercicio: int,
    source_ref: SourceRefId,
    source_content_digest: str,
    scope: str,
) -> None:
    """Require the pinned BOE source coordinate for 2022 annual authority."""
    if not (
        ejercicio == 2022
        and source_ref == _M303_2022_ORDEN_SOURCE_REF
        and source_content_digest == _M303_2022_ORDEN_SOURCE_DIGEST
    ):
        raise RegistryValidationError(f"annual Orden 2022 {scope} must retain its exact BOE source coordinate")


__all__ = [
    "EXTRACTOR_VERSION",
    "FIRST_SEASONAL_INDEX_DAY",
    "MINIMUM_SEASONAL_INDEX_BANDS",
    "validate_2022_annual_orden_coordinate",
    "validate_generated_source_axis_shape",
    "validate_generated_source_counts",
    "validate_percentage_shape",
    "validate_seasonal_index_shape",
]
