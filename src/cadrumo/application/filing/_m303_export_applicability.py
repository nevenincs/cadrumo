"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from ...core import Modelo, Period
from ...domain.calculations.registry import ExportLayoutDefinition, RegistrySnapshot
from ...domain.filing import FilingExportError
from ._producer_snapshot import FilingProducerSnapshot, assert_m303_regularisation_result_matches_bienes_register


def validate_m303_export_applicability(
    *,
    period: Period,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> None:
    """Validate canonical M303 facts against the already-selected snapshot."""
    try:
        FilingProducerSnapshot.model_validate(dict(producer_snapshot))
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 filing producer snapshot is incomplete: {exc}") from exc
    if producer_snapshot.modelo is not Modelo.M303:
        raise FilingExportError("Modelo 303 applicability received a non-303 producer snapshot")
    filing_facts = producer_snapshot.m303_filing_facts
    if filing_facts is None:
        raise FilingExportError("modelo 303 export requires internally assembled filing facts")
    if filing_facts.period != period:
        raise FilingExportError("modelo 303 filing facts do not match the export period")
    if (
        registry_snapshot.modelo.id != "303"
        or registry_snapshot.filing_year != period.filing_year
        or registry_snapshot.period != period.registry_token
    ):
        raise FilingExportError("modelo 303 applicability snapshot does not match the export period")
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportError("modelo 303 applicability layout is not owned by the selected snapshot")
    try:
        assert_m303_regularisation_result_matches_bienes_register(
            bienes_register=filing_facts.bienes_register,
            regularisation_result=filing_facts.regularisation_result,
        )
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 regularisation result is not canonical: {exc}") from exc


__all__ = ["validate_m303_export_applicability"]
