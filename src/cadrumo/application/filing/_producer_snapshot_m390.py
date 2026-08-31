"""Annual Modelo 390 filing arrivals owned by the producer snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, model_validator

from ...core.filing_projection_ref import (
    M390ActivityField,
    M390DifferentiatedDeductionProjectionField,
    M390ProrrataActivityProjectionField,
    M390RegimenSimplificadoActivityField,
    M390RegimenSimplificadoCohort,
    M390RegimenSimplificadoModuleValue,
    M390RepresentativeField,
    M390RepresentativeKind,
)
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period, StandardPeriodCode
from ...domain.calculations.registry.schema_references import SourceReference

type M390ProjectionScalar = str | Decimal | None


class M390ActivityValueArrival(BaseModel):
    """One source-shaped page-one statistical activity row."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int
    values: Mapping[M390ActivityField, M390ProjectionScalar]


class M390RepresentativeValueArrival(BaseModel):
    """One source-shaped physical/community or legal representative row."""

    model_config = STRICT_FROZEN_CONFIG

    representative_kind: M390RepresentativeKind
    slot: int
    values: Mapping[M390RepresentativeField, M390ProjectionScalar]


class M390RegimenSimplificadoActivityValueArrival(BaseModel):
    """One source-shaped page-five simplified-regime activity row."""

    model_config = STRICT_FROZEN_CONFIG

    cohort: M390RegimenSimplificadoCohort
    slot: int
    values: Mapping[M390RegimenSimplificadoActivityField, M390ProjectionScalar]


class M390RegimenSimplificadoModuleValueArrival(BaseModel):
    """One source-shaped module pair on a non-agricultural activity row."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int
    module_order: int
    values: Mapping[M390RegimenSimplificadoModuleValue, M390ProjectionScalar]


class M390ProrrataActivityValueArrival(BaseModel):
    """One source-shaped page-seven prorrata activity row."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int
    values: Mapping[M390ProrrataActivityProjectionField, M390ProjectionScalar]


class M390DifferentiatedDeductionValueArrival(BaseModel):
    """One source-shaped page-eight differentiated-deduction row."""

    model_config = STRICT_FROZEN_CONFIG

    slot: int
    values: Mapping[M390DifferentiatedDeductionProjectionField, M390ProjectionScalar]


class M390FilingFacts(BaseModel):
    """Complete source-shaped repeated-row arrivals for one annual Modelo 390 filing.

    Row values remain addressed by the closed core projection references. This
    layer therefore owns value arrival only; a semantic map later supplies the
    export-record coordinate without introducing a second M390 selector.
    """

    model_config = STRICT_FROZEN_CONFIG

    period: Period
    registry_revision_id: str
    record_design: SourceReference
    activity_rows: tuple[M390ActivityValueArrival, ...] = ()
    representative_rows: tuple[M390RepresentativeValueArrival, ...] = ()
    regimen_simplificado_activity_rows: tuple[M390RegimenSimplificadoActivityValueArrival, ...] = ()
    regimen_simplificado_module_rows: tuple[M390RegimenSimplificadoModuleValueArrival, ...] = ()
    prorrata_activity_rows: tuple[M390ProrrataActivityValueArrival, ...] = ()
    differentiated_deduction_rows: tuple[M390DifferentiatedDeductionValueArrival, ...] = ()

    @model_validator(mode="after")
    def _require_annual_period(self) -> M390FilingFacts:
        if self.period.standard_code is not StandardPeriodCode.ANNUAL:
            raise ValueError("M390 repeated-row filing facts require the annual 0A period")
        return self


__all__ = [
    "M390ActivityValueArrival",
    "M390DifferentiatedDeductionValueArrival",
    "M390FilingFacts",
    "M390ProjectionScalar",
    "M390ProrrataActivityValueArrival",
    "M390RegimenSimplificadoActivityValueArrival",
    "M390RegimenSimplificadoModuleValueArrival",
    "M390RepresentativeValueArrival",
]
