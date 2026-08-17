"""Shared shape constants and coordinate validation for annual Orden authority."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from ._errors import RegistryValidationError
from ._ids import RevisionId, SourceRefId

EXPECTED_ACTIVITY_COUNT = 49
EXPECTED_MODULE_COUNT = 141
EXPECTED_MODULE_DISTRIBUTION = {1: 2, 2: 25, 3: 12, 4: 4, 5: 1, 6: 3, 7: 2}
EXPECTED_MODULE_DISTRIBUTION_VECTOR = (2, 25, 12, 4, 1, 3, 2)
EXPECTED_NON_AGRICULTURAL_INGRESO_A_CUENTA_COUNT = 47
EXPECTED_AGRICULTURAL_AXIS_COUNTS = {2022: 16, 2023: 16, 2024: 16, 2025: 17, 2026: 17}
EXPECTED_SEASONAL_INDEXES = ((1, 60, Decimal("1.50")), (61, 120, Decimal("1.35")), (121, 180, Decimal("1.25")))
EXPECTED_DIFFICULT_JUSTIFICATION_PCT = Decimal("1")
SUPPORTED_EJERCICIOS = (2022, 2023, 2024, 2025, 2026)
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
    if source.seasonal_index_day_bands != tuple((start, end) for start, end, _ in EXPECTED_SEASONAL_INDEXES):
        raise RegistryValidationError("annual Orden manifest has the wrong seasonal index day bands")
    if source.seasonal_index_coefficients != tuple(value for _, _, value in EXPECTED_SEASONAL_INDEXES):
        raise RegistryValidationError("annual Orden manifest has the wrong seasonal index coefficients")
    if source.difficult_justification_pct != EXPECTED_DIFFICULT_JUSTIFICATION_PCT:
        raise RegistryValidationError("annual Orden manifest has the wrong difficult-justification percentage")
    if source.ejercicio == 2022:
        if source.lorca_2022_reduction_pct != Decimal("20"):
            raise RegistryValidationError("annual Orden manifest has the wrong Lorca 2022 reduction percentage")
    elif source.lorca_2022_reduction_pct is not None:
        raise RegistryValidationError("only the 2022 annual Orden manifest may state the Lorca reduction")


validate_generated_source_counts = _validate_generated_source_counts
validate_generated_source_axis_shape = _validate_generated_source_axis_shape

_M303_2022_REVISION_ID = "2009-2022"
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
