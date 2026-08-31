"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from .errors import ModeloApplicationError as FilingExportError
from .producer_snapshot import (
    FilingProducerSnapshot,
    M303FilingFacts,
    assert_m303_regularisation_result_matches_bienes_register,
)


def validate_m303_export_applicability(
    *,
    period: Period,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> None:
    """Validate canonical M303 facts against the already-selected snapshot."""
    _validate_producer_snapshot_shape(period, producer_snapshot)
    _require_m303_producer_snapshot(producer_snapshot)
    filing_facts = _require_m303_filing_facts(period, producer_snapshot)
    _validate_snapshot_selection(period, registry_snapshot, layout)
    _validate_m303_regularisation(period, filing_facts)


def _validate_producer_snapshot_shape(period: Period, producer_snapshot: FilingProducerSnapshot) -> None:
    try:
        FilingProducerSnapshot.model_validate(dict(producer_snapshot))
    except ValueError as exc:
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.producer_snapshot_incomplete",
            context={
                "modelo": Modelo.M303.value,
                "period": period.registry_token,
                "filing_year": period.filing_year,
                "validation_error_type": type(exc).__name__,
            },
        ) from exc


def _require_m303_producer_snapshot(producer_snapshot: FilingProducerSnapshot) -> None:
    if producer_snapshot.modelo is not Modelo.M303:
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.producer_snapshot_wrong_modelo",
            context={
                "expected_modelo": Modelo.M303.value,
                "actual_modelo": producer_snapshot.modelo.value,
            },
        )


def _require_m303_filing_facts(period: Period, producer_snapshot: FilingProducerSnapshot) -> M303FilingFacts:
    filing_facts = producer_snapshot.m303_filing_facts
    if filing_facts is None:
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.filing_facts_absent",
            context={
                "modelo": Modelo.M303.value,
                "period": period.registry_token,
                "filing_year": period.filing_year,
            },
        )
    if filing_facts.period != period:
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.filing_facts_period_mismatch",
            context={
                "modelo": Modelo.M303.value,
                "export_period": period.registry_token,
                "filing_facts_period": filing_facts.period.registry_token,
            },
        )

    return filing_facts


def _validate_snapshot_selection(
    period: Period,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
) -> None:
    if (
        registry_snapshot.modelo.id != Modelo.M303.value
        or registry_snapshot.filing_year != period.filing_year
        or registry_snapshot.period != period.registry_token
    ):
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.snapshot_period_mismatch",
            context={
                "expected_modelo": Modelo.M303.value,
                "snapshot_modelo": registry_snapshot.modelo.id,
                "export_period": period.registry_token,
                "snapshot_period": registry_snapshot.period,
                "export_filing_year": period.filing_year,
                "snapshot_filing_year": registry_snapshot.filing_year,
            },
        )
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.layout_not_snapshot_owned",
            context={
                "modelo": Modelo.M303.value,
                "layout_id": layout.id,
                "snapshot_layout_count": len(registry_snapshot.revision.export_layouts),
            },
        )


def _validate_m303_regularisation(period: Period, filing_facts: M303FilingFacts) -> None:
    try:
        assert_m303_regularisation_result_matches_bienes_register(
            bienes_register=filing_facts.bienes_register,
            regularisation_result=filing_facts.regularisation_result,
        )
    except ValueError as exc:
        raise FilingExportError(
            translated_message="application.filing.m303_export_applicability.errors.regularisation_result_not_canonical",
            context={
                "modelo": Modelo.M303.value,
                "period": period.registry_token,
                "validation_error_type": type(exc).__name__,
            },
        ) from exc


__all__ = ["validate_m303_export_applicability"]
