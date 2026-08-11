"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG, CasillaId, Period
from ...core.resources import resources
from ...domain.bienes_inversion import BienesInversionIvaRegister, RegistroRegularizacionResult
from ...domain.calculations.registry import RegistryValidationError, project_m303_differentiated_deduction_rows
from ...domain.filing import FilingExportError
from ...domain.prorrata_register import ProrrataRegister
from ..aggregation import IvaDifferentiatedDeductionContribution
from ._m303_prorrata_activity_rows import assert_m303_prorrata_activity_rows_complete
from ._m303_regimen_simplificado import (
    M303RegimenSimplificadoValueArrival,
    project_m303_regimen_simplificado_value_arrival,
)
from ._producer_snapshot import FilingProducerSnapshot
from .runtime import RegistrySchemaAccessor


class M303Exonerado390EndpointValue(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    casilla_id: CasillaId
    value: Decimal
    producer_reference: str = Field(min_length=1)


class M303Exonerado390ValueArrival(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    marker_reference: str = Field(min_length=1)
    endpoints: tuple[M303Exonerado390EndpointValue, ...] = Field(min_length=1)


class M303DifferentiatedSectorValueArrival(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    prorrata_register: ProrrataRegister
    contributions: tuple[IvaDifferentiatedDeductionContribution, ...]
    bienes_register: BienesInversionIvaRegister
    regularisation_result: RegistroRegularizacionResult


class M303ExportApplicabilityEnvelope(BaseModel):
    """Every conditional M303 export unit, with required explicit tri-state facts."""

    model_config = STRICT_FROZEN_CONFIG

    exonerado_390_applicable: bool | None
    exonerado_390: M303Exonerado390ValueArrival | None
    prorrata_activities_applicable: bool | None
    prorrata_register: ProrrataRegister | None
    differentiated_sectors_applicable: bool | None
    differentiated_sectors: M303DifferentiatedSectorValueArrival | None
    regimen_simplificado_applicable: bool | None
    regimen_simplificado: M303RegimenSimplificadoValueArrival | None

    @model_validator(mode="after")
    def _explicit_applicability_matches_payloads(self) -> M303ExportApplicabilityEnvelope:
        units = (
            ("exonerado 390", self.exonerado_390_applicable, self.exonerado_390),
            ("prorrata activities", self.prorrata_activities_applicable, self.prorrata_register),
            ("differentiated sectors", self.differentiated_sectors_applicable, self.differentiated_sectors),
            ("regimen simplificado", self.regimen_simplificado_applicable, self.regimen_simplificado),
        )
        for name, applicable, payload in units:
            if applicable is None:
                raise ValueError(f"modelo 303 {name} applicability must be explicitly resolved")
            if applicable and payload is None:
                raise ValueError(f"modelo 303 applicable {name} requires its authoritative payload")
            if not applicable and payload is not None:
                raise ValueError(f"modelo 303 non-applicable {name} must not carry a payload")
        return self


def validate_m303_export_applicability(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    producer_snapshot: FilingProducerSnapshot,
    envelope: M303ExportApplicabilityEnvelope,
) -> None:
    """Validate and project every conditional M303 unit before layout or target creation."""
    try:
        FilingProducerSnapshot.model_validate(dict(producer_snapshot))
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 filing producer snapshot is incomplete: {exc}") from exc
    snapshot = resources().modelos.authority.snapshot(
        "303", filing_year=period.filing_year, period=period.registry_token
    )
    if envelope.exonerado_390_applicable:
        arrival = envelope.exonerado_390
        assert arrival is not None
        expected = {
            casilla.id
            for casilla in snapshot.revision.casillas
            if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
        }
        actual = {item.casilla_id for item in arrival.endpoints}
        if len(actual) != len(arrival.endpoints) or actual != expected:
            raise FilingExportError("modelo 303 exonerado 390 endpoints/producers are incomplete or duplicate")
    if envelope.prorrata_activities_applicable:
        register = envelope.prorrata_register
        assert register is not None
        assert_m303_prorrata_activity_rows_complete(period=period, register=register)
    if envelope.differentiated_sectors_applicable:
        arrival = envelope.differentiated_sectors
        assert arrival is not None
        register_ids = {record.identifier for record in arrival.bienes_register.records}
        result_ids = {row.identifier for row in arrival.regularisation_result.rows}
        if not result_ids.issubset(register_ids):
            raise FilingExportError("modelo 303 differentiated regularisation lacks canonical Bienes register rows")
        try:
            project_m303_differentiated_deduction_rows(
                snapshot.revision,
                register=arrival.prorrata_register,
                ejercicio=period.filing_year,
                contributions=arrival.contributions,
                regularisation_result=arrival.regularisation_result,
            )
        except RegistryValidationError as exc:
            raise FilingExportError(f"modelo 303 differentiated sectors refused: {exc}") from exc
    if envelope.regimen_simplificado_applicable:
        arrival = envelope.regimen_simplificado
        assert arrival is not None
        project_m303_regimen_simplificado_value_arrival(
            period=period,
            schema_provider=schema_provider,
            value_arrival=arrival,
        )


__all__ = [
    "M303DifferentiatedSectorValueArrival",
    "M303Exonerado390EndpointValue",
    "M303Exonerado390ValueArrival",
    "M303ExportApplicabilityEnvelope",
    "validate_m303_export_applicability",
]
