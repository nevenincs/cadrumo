"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from ...core import Modelo, Period
from ...core.resources import resources
from ...domain.calculations.registry import RegistryValidationError, project_m303_differentiated_deduction_rows
from ...domain.filing import FilingExportError
from ._m303_exonerado_390 import project_m303_exonerado_390_value_arrival
from ._m303_prorrata_activity_rows import assert_m303_prorrata_activity_rows_complete
from ._producer_snapshot import FilingProducerSnapshot, assert_m303_regularisation_result_matches_bienes_register
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
    if producer_snapshot.modelo is not Modelo.M303:
        raise FilingExportError("Modelo 303 applicability received a non-303 producer snapshot")
    filing_facts = producer_snapshot.m303_filing_facts
    if filing_facts is None:
        raise FilingExportError("modelo 303 export requires internally assembled filing facts")
    if filing_facts.period != period:
        raise FilingExportError("modelo 303 filing facts do not match the export period")
    try:
        assert_m303_regularisation_result_matches_bienes_register(
            bienes_register=filing_facts.bienes_register,
            regularisation_result=filing_facts.regularisation_result,
        )
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 regularisation result is not canonical: {exc}") from exc

    snapshot = resources().modelos.authority.snapshot(
        "303", filing_year=period.filing_year, period=period.registry_token
    )
    if filing_facts.exonerado_390.applicable:
        expected = {
            casilla.id
            for casilla in snapshot.revision.casillas
            if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
        }
        actual = {endpoint.casilla_id for endpoint in filing_facts.exonerado_390.endpoints}
        if len(actual) != len(filing_facts.exonerado_390.endpoints) or actual != expected:
            raise FilingExportError("modelo 303 exonerado 390 evidenced endpoints are incomplete or duplicate")
    project_m303_exonerado_390_value_arrival(
        period=period,
        schema_provider=schema_provider,
        evidence=filing_facts.exonerado_390,
        record_design=filing_facts.regimen_simplificado.regimen_snapshot.record_design,
    )
    register = filing_facts.prorrata_register
    if register.requires_activity_rows_for(period.filing_year):
        assert_m303_prorrata_activity_rows_complete(period=period, register=register)
    if register.is_sectorized:
        try:
            project_m303_differentiated_deduction_rows(
                snapshot.revision,
                register=register,
                ejercicio=period.filing_year,
                contributions=filing_facts.differentiated_contributions,
                regularisation_result=filing_facts.regularisation_result,
            )
        except RegistryValidationError as exc:
            raise FilingExportError(f"modelo 303 differentiated sectors refused: {exc}") from exc


__all__ = ["validate_m303_export_applicability"]
