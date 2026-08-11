"""Canonical typed references from official record fields to repeated filing facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ._casilla_id import CasillaId
from ._models import STRICT_FROZEN_CONFIG

_Identity = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*[a-z0-9]$|^[a-z0-9]$",
    ),
]


class M303ProrrataActivityProjectionField(StrEnum):
    """Closed fields projected from one canonical prorrata activity row."""

    CNAE = "cnae"
    OPERACIONES_TOTAL = "operaciones_total"
    OPERACIONES_CON_DERECHO = "operaciones_con_derecho"
    TIPO = "tipo"
    PORCENTAJE = "porcentaje"


class M303DifferentiatedDeductionProjectionField(StrEnum):
    """Closed fields projected from one differentiated-sector deduction row."""

    DOMESTIC_CURRENT_BASE = "domestic_current_base"
    DOMESTIC_CURRENT_CUOTA = "domestic_current_cuota"
    DOMESTIC_INVESTMENT_BASE = "domestic_investment_base"
    DOMESTIC_INVESTMENT_CUOTA = "domestic_investment_cuota"
    IMPORT_CURRENT_BASE = "import_current_base"
    IMPORT_CURRENT_CUOTA = "import_current_cuota"
    IMPORT_INVESTMENT_BASE = "import_investment_base"
    IMPORT_INVESTMENT_CUOTA = "import_investment_cuota"
    INTRA_EU_CURRENT_BASE = "intra_eu_current_base"
    INTRA_EU_CURRENT_CUOTA = "intra_eu_current_cuota"
    INTRA_EU_INVESTMENT_BASE = "intra_eu_investment_base"
    INTRA_EU_INVESTMENT_CUOTA = "intra_eu_investment_cuota"
    REAGP_BASE = "reagp_base"
    REAGP_CUOTA = "reagp_cuota"
    RECTIFICATION_BASE = "rectification_base"
    RECTIFICATION_CUOTA = "rectification_cuota"
    INVESTMENT_REGULARISATION = "investment_regularisation"
    TOTAL = "total"


class M303RegimenSimplificadoCohort(StrEnum):
    """Closed simplified-regime activity cohorts printed in DP30302."""

    AGRICOLA = "agricola"
    NO_AGRICOLA = "no_agricola"


class M303RegimenSimplificadoActivityField(StrEnum):
    """Closed identity fields projected directly from an activity row."""

    ACTIVITY_CODE = "activity_code"
    IAE_EPIGRAFE = "iae_epigrafe"


class M303RegimenSimplificadoModuleValue(StrEnum):
    """Closed values addressable on one annual-Orden module."""

    DECLARED_QUANTITY = "declared_quantity"
    OFF_FORM_RESULT = "off_form_result"


class M303Exonerado390ActivityField(StrEnum):
    """Closed fields projected from one evidenced exonerado-390 activity row."""

    ACTIVITY_CODE = "activity_code"
    IAE_EPIGRAFE = "iae_epigrafe"


class M303ProrrataActivityProjectionRef(BaseModel):
    """One exact numbered endpoint on a canonical prorrata activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_prorrata_activity"] = "m303_prorrata_activity"
    slot: int = Field(ge=1, le=5)
    field: M303ProrrataActivityProjectionField
    casilla_id: CasillaId


class M303DifferentiatedDeductionProjectionRef(BaseModel):
    """One exact numbered endpoint on a differentiated-sector row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_differentiated_deduction"] = "m303_differentiated_deduction"
    slot: int = Field(ge=1, le=2)
    field: M303DifferentiatedDeductionProjectionField
    casilla_id: CasillaId


class M303RegimenSimplificadoActivityProjectionRef(BaseModel):
    """One direct identity field on a simplified-regime activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_activity"] = "m303_regimen_simplificado_activity"
    cohort: M303RegimenSimplificadoCohort
    slot: int = Field(ge=1, le=2)
    field: M303RegimenSimplificadoActivityField

    @model_validator(mode="after")
    def _cohort_owns_field(self) -> M303RegimenSimplificadoActivityProjectionRef:
        expected = (
            M303RegimenSimplificadoActivityField.ACTIVITY_CODE
            if self.cohort is M303RegimenSimplificadoCohort.AGRICOLA
            else M303RegimenSimplificadoActivityField.IAE_EPIGRAFE
        )
        if self.field is not expected:
            raise ValueError(f"simplified-regime cohort {self.cohort.value!r} requires field {expected.value!r}")
        return self


class M303RegimenSimplificadoFactProjectionRef(BaseModel):
    """One annual-Orden fact on a simplified-regime activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_fact"] = "m303_regimen_simplificado_fact"
    cohort: M303RegimenSimplificadoCohort
    slot: int = Field(ge=1, le=2)
    fact_identity: _Identity


class M303RegimenSimplificadoModuleProjectionRef(BaseModel):
    """One typed value on an annual-Orden module address."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_module"] = "m303_regimen_simplificado_module"
    cohort: Literal[M303RegimenSimplificadoCohort.NO_AGRICOLA] = M303RegimenSimplificadoCohort.NO_AGRICOLA
    slot: int = Field(ge=1, le=2)
    module_identity: _Identity
    value: M303RegimenSimplificadoModuleValue


class M303Exonerado390ActivityProjectionRef(BaseModel):
    """One exact field on an evidenced exonerado-390 activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_exonerado_390_activity"] = "m303_exonerado_390_activity"
    slot: int = Field(ge=1, le=6)
    field: M303Exonerado390ActivityField


class M303Exonerado390OperacionesTercerosProjectionRef(BaseModel):
    """The evidenced Modelo 347 marker printed after exonerado activity rows."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_exonerado_390_operaciones_terceros"] = (
        "m303_exonerado_390_operaciones_terceros"
    )


FilingProjectionRef = Annotated[
    M303ProrrataActivityProjectionRef
    | M303DifferentiatedDeductionProjectionRef
    | M303RegimenSimplificadoActivityProjectionRef
    | M303RegimenSimplificadoFactProjectionRef
    | M303RegimenSimplificadoModuleProjectionRef
    | M303Exonerado390ActivityProjectionRef
    | M303Exonerado390OperacionesTercerosProjectionRef,
    Field(discriminator="projection_kind"),
]
"""Strict core-owned union for every repeated-row filing projection."""


__all__ = [
    "FilingProjectionRef",
    "M303DifferentiatedDeductionProjectionField",
    "M303DifferentiatedDeductionProjectionRef",
    "M303Exonerado390ActivityField",
    "M303Exonerado390ActivityProjectionRef",
    "M303Exonerado390OperacionesTercerosProjectionRef",
    "M303ProrrataActivityProjectionField",
    "M303ProrrataActivityProjectionRef",
    "M303RegimenSimplificadoActivityField",
    "M303RegimenSimplificadoActivityProjectionRef",
    "M303RegimenSimplificadoCohort",
    "M303RegimenSimplificadoFactProjectionRef",
    "M303RegimenSimplificadoModuleProjectionRef",
    "M303RegimenSimplificadoModuleValue",
]
