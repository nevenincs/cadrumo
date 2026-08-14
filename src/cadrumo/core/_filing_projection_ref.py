"""Canonical typed references from official record fields to repeated filing facts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, model_validator

from ._casilla_id import CasillaId
from ._models import STRICT_FROZEN_CONFIG

_Identity = Annotated[
    str,
    StringConstraints(
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
    AUXILIARY_ACTIVITY_INDICATOR = "auxiliary_activity_indicator"


class M303RegimenSimplificadoModuleValue(StrEnum):
    """Closed input and calculated values addressable on one annual-Orden module."""

    DECLARED_QUANTITY = "declared_quantity"
    CUOTA_DEVENGADA = "cuota_devengada"


class M303RegimenSimplificadoFact(StrEnum):
    """Closed semantic facts printed by the DP30302 simplified-regime record."""

    VOLUMEN_INGRESOS = "volumen_ingresos"
    INDICE_CUOTA = "indice_cuota"
    CUOTA_DEVENGADA = "cuota_devengada"
    PORCENTAJE_INGRESO_CUENTA = "porcentaje_ingreso_cuenta"
    INGRESO_CUENTA = "ingreso_cuenta"
    CUOTA_SOPORTADA_OPERACIONES_CORRIENTES = "cuota_soportada_operaciones_corrientes"
    CUOTAS_SOPORTADAS_OPERACIONES_CORRIENTES = "cuotas_soportadas_operaciones_corrientes"
    CUOTA_ANUAL_DERIVADA_REGIMEN_SIMPLIFICADO = "cuota_anual_derivada_regimen_simplificado"
    CUOTAS_SOPORTADAS_CUARTO_TRIMESTRE = "cuotas_soportadas_cuarto_trimestre"
    COMPENSACIONES_REAGP_CUARTO_TRIMESTRE = "compensaciones_reagp_cuarto_trimestre"
    DANA_ELEGIBLE = "dana_elegible"
    REDUCCION_DANA = "reduccion_dana"
    CUOTA_DEVENGADA_OPERACIONES_CORRIENTES = "cuota_devengada_operaciones_corrientes"
    REDUCCIONES = "reducciones"
    INDICE_CORRECTOR_ACTIVIDAD_TEMPORADA = "indice_corrector_actividad_temporada"
    INDICE_CORRECTOR_ACTIVIDADES_TEMPORADA = "indice_corrector_actividades_temporada"
    RESULTADO_CUARTO_TRIMESTRE = "resultado_cuarto_trimestre"
    PORCENTAJE_CUOTA_MINIMA = "porcentaje_cuota_minima"
    DEVOLUCION_CUOTAS_SOPORTADAS_OTROS_PAISES = "devolucion_cuotas_soportadas_otros_paises"
    CUOTA_MINIMA = "cuota_minima"
    ACTIVIDAD_TEMPORADA_DIAS_EJERCICIO_ANIO_ANTERIOR = "actividad_temporada_dias_ejercicio_anio_anterior"
    DIAS_EJERCICIO_TRIMESTRE = "dias_ejercicio_trimestre"
    EMPLEADOS_INICIO_EJERCICIO = "empleados_inicio_ejercicio"
    EMPLEADOS_INICIO_EJERCICIO_ACTUAL = "empleados_inicio_ejercicio_actual"
    ACTIVIDAD_TEMPORADA_DIAS_EJERCICIO_CUARTO_TRIMESTRE = "actividad_temporada_dias_ejercicio_cuarto_trimestre"
    MAX_ASALARIADOS_SIMULTANEOS = "max_asalariados_simultaneos"
    LORCA_ELEGIBLE = "lorca_elegible"
    REDUCCION_LORCA = "reduccion_lorca"
    PERSONAL_ASALARIADO_HORAS_MAYORES_19 = "personal_asalariado_horas_mayores_19"
    PERSONAL_ASALARIADO_HORAS_MENORES_19_O_FORMACION = "personal_asalariado_horas_menores_19_o_formacion"
    PERSONAL_ASALARIADO_HORAS_DISCAPACIDAD_33 = "personal_asalariado_horas_discapacidad_33"
    PERSONAL_ASALARIADO_HORAS_CONVENIO_COLECTIVO = "personal_asalariado_horas_convenio_colectivo"
    PERSONAL_NO_ASALARIADO_HORAS_TITULAR = "personal_no_asalariado_horas_titular"
    PERSONAL_NO_ASALARIADO_TITULAR_DISCAPACIDAD_33 = "personal_no_asalariado_titular_discapacidad_33"
    PERSONAL_NO_ASALARIADO_HORAS_CONYUGE = "personal_no_asalariado_horas_conyuge"
    PERSONAL_NO_ASALARIADO_HORAS_HIJOS_MENORES_18 = "personal_no_asalariado_horas_hijos_menores_18"
    MESAS_CAPACIDAD = "mesas_capacidad"
    MESAS_NUMERO = "mesas_numero"
    MESAS_DIAS_CUARTO_TRIMESTRE = "mesas_dias_cuarto_trimestre"
    SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE = "superficie_horno_dias_cuarto_trimestre"
    SUPERFICIE_HORNO_CUARTO_TRIMESTRE = "superficie_horno_cuarto_trimestre"


_M303_REGIMEN_SIMPLIFICADO_REPEATING_FACTS = frozenset(
    {
        M303RegimenSimplificadoFact.MESAS_CAPACIDAD,
        M303RegimenSimplificadoFact.MESAS_DIAS_CUARTO_TRIMESTRE,
        M303RegimenSimplificadoFact.MESAS_NUMERO,
        M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE,
        M303RegimenSimplificadoFact.SUPERFICIE_HORNO_CUARTO_TRIMESTRE,
    },
)


class M303Exonerado390ActivityField(StrEnum):
    """Closed fields projected from one evidenced exonerado-390 activity row."""

    ACTIVITY_CODE = "activity_code"
    IAE_EPIGRAFE = "iae_epigrafe"


class M303ProrrataActivityProjectionRef(BaseModel):
    """One exact numbered endpoint on a canonical prorrata activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_prorrata_activity"]
    slot: int = Field(ge=1, le=5)
    field: M303ProrrataActivityProjectionField
    casilla_id: CasillaId


class M303DifferentiatedDeductionProjectionRef(BaseModel):
    """One exact numbered endpoint on a differentiated-sector row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_differentiated_deduction"]
    slot: int = Field(ge=1, le=2)
    field: M303DifferentiatedDeductionProjectionField
    casilla_id: CasillaId


class M303RegimenSimplificadoActivityProjectionRef(BaseModel):
    """One direct identity field on a simplified-regime activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_activity"]
    cohort: M303RegimenSimplificadoCohort
    slot: int = Field(ge=1, le=2)
    field: M303RegimenSimplificadoActivityField

    @model_validator(mode="after")
    def _cohort_owns_field(self) -> M303RegimenSimplificadoActivityProjectionRef:
        allowed = (
            {M303RegimenSimplificadoActivityField.ACTIVITY_CODE}
            if self.cohort is M303RegimenSimplificadoCohort.AGRICOLA
            else {
                M303RegimenSimplificadoActivityField.IAE_EPIGRAFE,
                M303RegimenSimplificadoActivityField.AUXILIARY_ACTIVITY_INDICATOR,
            }
        )
        if self.field not in allowed:
            raise ValueError(
                f"simplified-regime cohort {self.cohort.value!r} requires field in its owned set; "
                f"got {self.field.value!r}"
            )
        return self


class M303RegimenSimplificadoFactProjectionRef(BaseModel):
    """One closed semantic fact at a simplified-regime cohort and slot."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_fact"]
    cohort: M303RegimenSimplificadoCohort
    slot: int = Field(ge=1, le=2)
    fact: M303RegimenSimplificadoFact
    sub_index: int | None = Field(default=None, ge=1, le=4)

    @model_validator(mode="after")
    def _require_the_closed_multiplicity_axis(self) -> M303RegimenSimplificadoFactProjectionRef:
        if self.fact not in _M303_REGIMEN_SIMPLIFICADO_REPEATING_FACTS and self.sub_index is not None:
            raise ValueError("a singleton simplified-regime fact must not carry sub_index")
        if (
            self.fact
            in {
                M303RegimenSimplificadoFact.MESAS_CAPACIDAD,
                M303RegimenSimplificadoFact.MESAS_DIAS_CUARTO_TRIMESTRE,
                M303RegimenSimplificadoFact.MESAS_NUMERO,
            }
            and self.sub_index is None
        ):
            raise ValueError("a Mesa simplified-regime fact requires sub_index")
        return self


class M303RegimenSimplificadoModuleProjectionRef(BaseModel):
    """One typed value at an annual-Orden module ordinal."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_regimen_simplificado_module"]
    cohort: Literal[M303RegimenSimplificadoCohort.NO_AGRICOLA]
    slot: int = Field(ge=1, le=2)
    module_order: int = Field(ge=1, le=7)
    value: M303RegimenSimplificadoModuleValue


class M303Exonerado390ActivityProjectionRef(BaseModel):
    """One exact field on an evidenced exonerado-390 activity row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_exonerado_390_activity"]
    slot: int = Field(ge=1, le=6)
    field: M303Exonerado390ActivityField


class M303Exonerado390OperacionesTercerosProjectionRef(BaseModel):
    """The evidenced Modelo 347 marker printed after exonerado activity rows."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m303_exonerado_390_operaciones_terceros"]


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

_FILING_PROJECTION_REF_ADAPTER: TypeAdapter[FilingProjectionRef] = TypeAdapter(FilingProjectionRef)
_STRING_WIRE_FIELDS = frozenset(
    {
        "casilla_id",
        "cohort",
        "fact",
        "field",
        "projection_kind",
        "value",
    },
)


def compile_filing_projection_ref(value: object) -> FilingProjectionRef:
    """Compile one canonical projection reference from exact persisted primitives."""
    if not isinstance(value, Mapping):
        raise ValueError("filing projection reference must be a mapping")
    source = cast(Mapping[object, object], value)
    payload: dict[str, object] = {}
    for raw_key, raw_value in source.items():
        if type(raw_key) is not str:
            raise ValueError("filing projection reference keys must be exact strings")
        payload[raw_key] = raw_value
    for field_name in _STRING_WIRE_FIELDS.intersection(payload):
        if type(payload[field_name]) is not str:
            raise ValueError(f"filing projection reference {field_name!r} must be an exact string")
        string_value = cast(str, payload[field_name])
        if string_value != string_value.strip():
            raise ValueError(f"filing projection reference {field_name!r} must not contain surrounding whitespace")
    for integer_field in ("slot", "module_order", "sub_index"):
        if integer_field in payload and type(payload[integer_field]) is not int:
            raise ValueError(f"filing projection reference {integer_field!r} must be an exact integer")
    return _FILING_PROJECTION_REF_ADAPTER.validate_python(payload, strict=False)


def filing_projection_ref_casilla_id(reference: FilingProjectionRef) -> CasillaId | None:
    """Return the numbered official endpoint carried by ``reference``, if any."""
    if isinstance(reference, M303ProrrataActivityProjectionRef | M303DifferentiatedDeductionProjectionRef):
        return reference.casilla_id
    return None


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
    "M303RegimenSimplificadoFact",
    "M303RegimenSimplificadoFactProjectionRef",
    "M303RegimenSimplificadoModuleProjectionRef",
    "M303RegimenSimplificadoModuleValue",
    "compile_filing_projection_ref",
    "filing_projection_ref_casilla_id",
]
