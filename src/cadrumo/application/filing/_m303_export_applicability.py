"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from ...core import Period
from ...domain.filing import FilingExportError
from ._producer_snapshot import FilingProducerSnapshot
from .runtime import RegistrySchemaAccessor


def validate_m303_export_applicability(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    producer_snapshot: FilingProducerSnapshot,
) -> None:
    """Validate canonical M303 facts assembled internally before any export write."""
    try:
        FilingProducerSnapshot.model_validate(dict(producer_snapshot))
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 filing producer snapshot is incomplete: {exc}") from exc
    del period, schema_provider
    raise FilingExportError(
        "modelo 303 export awaits the canonical S55 producer snapshot; "
        "filing evidence must not assemble or infer that producer boundary",
    )


__all__ = ["validate_m303_export_applicability"]
