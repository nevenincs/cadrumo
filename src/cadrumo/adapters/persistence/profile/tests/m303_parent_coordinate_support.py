"""The Modelo 303 / 2026 / 1T registry coordinate and work-unit identity calculation-revision suites share."""

from __future__ import annotations

from functools import cache

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

from .published_authority_support import published_authority_operation


@cache
def registry_snapshot_ref() -> RegistrySnapshotRef:
    # Compiled on first use, not at import: collection must stay cheap.
    return published_authority_operation().snapshot("303", filing_year=2026, period="1T").snapshot_ref


@cache
def work_unit_period() -> Period:
    ref = registry_snapshot_ref()
    return Period.from_year_and_code(ref.modelo_year, ref.period)


@cache
def parent_work_unit_id(bucket_id: str) -> str:
    ref = registry_snapshot_ref()
    return derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=ref.modelo,
        filing_year=ref.modelo_year,
        period=work_unit_period(),
        revision_id=ref.revision_id,
    )
