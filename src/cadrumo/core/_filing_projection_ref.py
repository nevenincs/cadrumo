"""Canonical typed references from official record fields to repeated filing facts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Final, Literal, cast, get_args

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, model_validator

from .casilla_id import CasillaId
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


M303_MESA_FACTS: frozenset[M303RegimenSimplificadoFact] = frozenset(
    {
        M303RegimenSimplificadoFact.MESAS_CAPACIDAD,
        M303RegimenSimplificadoFact.MESAS_DIAS_CUARTO_TRIMESTRE,
        M303RegimenSimplificadoFact.MESAS_NUMERO,
    },
)
"""Facts that repeat once per mesa (table). A mesa fact therefore REQUIRES a
``sub_index`` identifying which mesa it describes."""


M303_REPEATING_FACTS: frozenset[M303RegimenSimplificadoFact] = M303_MESA_FACTS | frozenset(
    {
        M303RegimenSimplificadoFact.SUPERFICIE_HORNO_DIAS_CUARTO_TRIMESTRE,
        M303RegimenSimplificadoFact.SUPERFICIE_HORNO_CUARTO_TRIMESTRE,
    },
)
"""Every fact that repeats per unit at all -- :data:`M303_MESA_FACTS` plus the
horno (oven) facts, which repeat per horno rather than per mesa. A fact
outside this set is a singleton and must NOT carry a ``sub_index``."""


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
        if self.fact not in M303_REPEATING_FACTS and self.sub_index is not None:
            raise ValueError("a singleton simplified-regime fact must not carry sub_index")
        if self.fact in M303_MESA_FACTS and self.sub_index is None:
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


class M390ActivityField(StrEnum):
    """Closed identity fields of one page-one statistical activity row."""

    DESCRIPTION = "description"
    ACTIVITY_CODE = "activity_code"
    IAE_EPIGRAFE = "iae_epigrafe"


class M390ActivityProjectionRef(BaseModel):
    """One field of the fixed six-row statistical-activity block on page one."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_activity"]
    slot: int = Field(ge=1, le=6)
    field: M390ActivityField


class M390RepresentativeKind(StrEnum):
    """The two non-interchangeable official representative blocks on page one."""

    FISICA_COMUNIDAD_BIENES = "fisica_comunidad_bienes"
    JURIDICA = "juridica"


class M390RepresentativeField(StrEnum):
    """Closed fields printed by one physical or legal representative row."""

    NIF = "nif"
    NOMBRE_RAZON_SOCIAL = "nombre_razon_social"
    TIPO_VIA = "tipo_via"
    NOMBRE_VIA = "nombre_via"
    NUMERO_VIA = "numero_via"
    ESCALERA = "escalera"
    PISO = "piso"
    PUERTA = "puerta"
    TELEFONO = "telefono"
    MUNICIPIO = "municipio"
    PROVINCIA = "provincia"
    CODIGO_POSTAL = "codigo_postal"
    FECHA_PODER = "fecha_poder"
    NOTARIA = "notaria"


_M390_PHYSICAL_REPRESENTATIVE_FIELDS = frozenset(
    {
        M390RepresentativeField.NIF,
        M390RepresentativeField.NOMBRE_RAZON_SOCIAL,
        M390RepresentativeField.TIPO_VIA,
        M390RepresentativeField.NOMBRE_VIA,
        M390RepresentativeField.NUMERO_VIA,
        M390RepresentativeField.ESCALERA,
        M390RepresentativeField.PISO,
        M390RepresentativeField.PUERTA,
        M390RepresentativeField.TELEFONO,
        M390RepresentativeField.MUNICIPIO,
        M390RepresentativeField.PROVINCIA,
        M390RepresentativeField.CODIGO_POSTAL,
    },
)
_M390_LEGAL_REPRESENTATIVE_FIELDS = frozenset(
    {
        M390RepresentativeField.NOMBRE_RAZON_SOCIAL,
        M390RepresentativeField.NIF,
        M390RepresentativeField.FECHA_PODER,
        M390RepresentativeField.NOTARIA,
    },
)


class M390RepresentativeProjectionRef(BaseModel):
    """One source-shaped page-one representative field.

    Natural-person/community representation has one address-shaped row;
    juridical persons have three compact power/notary rows.  Keeping those
    shapes in one discriminated projection prevents a caller from creating a
    fictitious fourth legal representative or a second physical address row.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_representative"]
    representative_kind: M390RepresentativeKind
    slot: int = Field(ge=1, le=3)
    field: M390RepresentativeField

    @model_validator(mode="after")
    def _require_source_declared_representative_shape(self) -> M390RepresentativeProjectionRef:
        if self.representative_kind is M390RepresentativeKind.FISICA_COMUNIDAD_BIENES:
            if self.slot != 1 or self.field not in _M390_PHYSICAL_REPRESENTATIVE_FIELDS:
                raise ValueError("physical/community representative requires its one address-shaped source row")
            return self
        if self.field not in _M390_LEGAL_REPRESENTATIVE_FIELDS:
            raise ValueError("legal representative requires one of its compact source-row fields")
        return self


class M390RegimenSimplificadoCohort(StrEnum):
    """The two distinct simplified-regime activity blocks on page five."""

    NO_AGRICOLA = "no_agricola"
    AGRICOLA_GANADERA = "agricola_ganadera"


class M390RegimenSimplificadoActivityField(StrEnum):
    """Closed source fields for one simplified-regime activity row."""

    IAE_EPIGRAFE = "iae_epigrafe"
    AUXILIARY_ACTIVITY_INDICATOR = "auxiliary_activity_indicator"
    CUOTA_DEVENGADA_OPERACIONES_CORRIENTES = "cuota_devengada_operaciones_corrientes"
    REDUCCION_LORCA = "reduccion_lorca"
    CUOTA_SOPORTADA_OPERACIONES_CORRIENTES = "cuota_soportada_operaciones_corrientes"
    INDICE_CORRECTOR = "indice_corrector"
    RESULTADO = "resultado"
    PORCENTAJE_CUOTA_MINIMA = "porcentaje_cuota_minima"
    DEVOLUCION_CUOTAS_SOPORTADAS_OTROS_PAISES = "devolucion_cuotas_soportadas_otros_paises"
    CUOTA_MINIMA = "cuota_minima"
    ACTIVITY_CODE = "activity_code"
    VOLUMEN_INGRESOS = "volumen_ingresos"
    INDICE_CUOTA = "indice_cuota"
    CUOTA_DEVENGADA = "cuota_devengada"
    CUOTA_SOPORTADA = "cuota_soportada"
    CUOTA_DERIVADA_REGIMEN_SIMPLIFICADO = "cuota_derivada_regimen_simplificado"


_M390_NO_AGRICOLA_SIMPLIFICADO_FIELDS = frozenset(
    {
        M390RegimenSimplificadoActivityField.IAE_EPIGRAFE,
        M390RegimenSimplificadoActivityField.AUXILIARY_ACTIVITY_INDICATOR,
        M390RegimenSimplificadoActivityField.CUOTA_DEVENGADA_OPERACIONES_CORRIENTES,
        M390RegimenSimplificadoActivityField.REDUCCION_LORCA,
        M390RegimenSimplificadoActivityField.CUOTA_SOPORTADA_OPERACIONES_CORRIENTES,
        M390RegimenSimplificadoActivityField.INDICE_CORRECTOR,
        M390RegimenSimplificadoActivityField.RESULTADO,
        M390RegimenSimplificadoActivityField.PORCENTAJE_CUOTA_MINIMA,
        M390RegimenSimplificadoActivityField.DEVOLUCION_CUOTAS_SOPORTADAS_OTROS_PAISES,
        M390RegimenSimplificadoActivityField.CUOTA_MINIMA,
        M390RegimenSimplificadoActivityField.CUOTA_DERIVADA_REGIMEN_SIMPLIFICADO,
    },
)
_M390_AGRICOLA_SIMPLIFICADO_FIELDS = frozenset(
    {
        M390RegimenSimplificadoActivityField.ACTIVITY_CODE,
        M390RegimenSimplificadoActivityField.VOLUMEN_INGRESOS,
        M390RegimenSimplificadoActivityField.INDICE_CUOTA,
        M390RegimenSimplificadoActivityField.CUOTA_DEVENGADA,
        M390RegimenSimplificadoActivityField.CUOTA_SOPORTADA,
        M390RegimenSimplificadoActivityField.CUOTA_DERIVADA_REGIMEN_SIMPLIFICADO,
    },
)


class M390RegimenSimplificadoActivityProjectionRef(BaseModel):
    """One source-shaped endpoint on a page-five simplified-regime activity."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_regimen_simplificado_activity"]
    cohort: M390RegimenSimplificadoCohort
    slot: int = Field(ge=1, le=5)
    field: M390RegimenSimplificadoActivityField

    @model_validator(mode="after")
    def _require_source_declared_cohort_shape(self) -> M390RegimenSimplificadoActivityProjectionRef:
        if self.cohort is M390RegimenSimplificadoCohort.NO_AGRICOLA:
            if self.slot > 2 or self.field not in _M390_NO_AGRICOLA_SIMPLIFICADO_FIELDS:
                raise ValueError("non-agricultural simplified activity requires one of its two source rows and fields")
            return self
        if self.field not in _M390_AGRICOLA_SIMPLIFICADO_FIELDS:
            raise ValueError("agricultural simplified activity requires one of its five source rows and fields")
        return self


class M390RegimenSimplificadoModuleValue(StrEnum):
    """The paired module inputs printed for each non-agricultural activity."""

    UNITS = "units"
    IMPORTE = "importe"


class M390RegimenSimplificadoModuleProjectionRef(BaseModel):
    """One of seven numbered module pairs on either non-agricultural activity."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_regimen_simplificado_module"]
    slot: int = Field(ge=1, le=2)
    module_order: int = Field(ge=1, le=7)
    value: M390RegimenSimplificadoModuleValue


class M390ProrrataActivityProjectionField(StrEnum):
    """Closed fields on one of the five page-seven prorrata activity rows."""

    ACTIVITY_DESCRIPTION = "activity_description"
    CNAE = "cnae"
    OPERACIONES_TOTAL = "operaciones_total"
    OPERACIONES_CON_DERECHO = "operaciones_con_derecho"
    TIPO = "tipo"
    PORCENTAJE = "porcentaje"


class M390ProrrataActivityProjectionRef(BaseModel):
    """One source-shaped page-seven prorrata endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_prorrata_activity"]
    slot: int = Field(ge=1, le=5)
    field: M390ProrrataActivityProjectionField


class M390DifferentiatedDeductionProjectionField(StrEnum):
    """Closed deduction fields on one of the three differentiated-sector rows."""

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


class M390DifferentiatedDeductionProjectionRef(BaseModel):
    """One page-eight endpoint on one of three differentiated deduction sectors."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m390_differentiated_deduction"]
    slot: int = Field(ge=1, le=3)
    field: M390DifferentiatedDeductionProjectionField


class M200EstablecimientoPermanenteField(StrEnum):
    """Closed fields of one detail row for a permanent establishment abroad."""

    IDENTIFICACION = "identificacion"
    PAIS_RESIDENCIA_FISCAL = "pais_residencia_fiscal"
    VOLUMEN_OPERACIONES = "volumen_operaciones"
    BENEFICIO_O_PERDIDA = "beneficio_o_perdida"
    SUMA_AJUSTES_RESULTADO_CONTABLE = "suma_ajustes_resultado_contable"
    SUMA_DEDUCCIONES_DI_INTERNACIONAL_ANTERIORES = "suma_deducciones_di_internacional_anteriores"


class M200EstablecimientoPermanenteProjectionRef(BaseModel):
    """One numbered establecimiento permanente detail row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_establecimiento_permanente"]
    slot: int = Field(ge=1, le=18)
    field: M200EstablecimientoPermanenteField


class M200SocioSicavDisolucionField(StrEnum):
    """Closed fields of one SICAV disolucion socio row."""

    NIF_SOCIEDAD_DISUELTA = "nif_sociedad_disuelta"
    NIF_IIC_REINVERSION = "nif_iic_reinversion"


class M200SocioSicavDisolucionProjectionRef(BaseModel):
    """One numbered socio row of the SICAV disolucion y liquidacion regime."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_socio_sicav_disolucion"]
    slot: int = Field(ge=1, le=5)
    field: M200SocioSicavDisolucionField


class M200EntidadMenorDependienteField(StrEnum):
    """Closed fields of one dependent minor ecclesiastical entity row."""

    NIF = "nif"
    NOMBRE_O_RAZON_SOCIAL = "nombre_o_razon_social"


class M200EntidadMenorDependienteProjectionRef(BaseModel):
    """One numbered entidad menor dependiente row.

    AEAT numbers these "Entidad 1", "Entidad 2" in the field's own description
    rather than with a bracketed or dotted index, which is why an earlier pass
    mistook the run for an unnumbered one.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_entidad_menor_dependiente"]
    slot: int = Field(ge=1, le=10)
    field: M200EntidadMenorDependienteField


class M200IncnGrupoSociedadField(StrEnum):
    """Closed fields of one group-company row of the INCN communication."""

    NIF_ENTIDAD_GRUPO = "nif_entidad_grupo"
    CODIGO_PAIS = "codigo_pais"


class M200IncnGrupoSociedadProjectionRef(BaseModel):
    """One numbered group company in the importe neto cifra negocios block."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_incn_grupo_sociedad"]
    slot: int = Field(ge=1, le=12)
    field: M200IncnGrupoSociedadField


class M200IncnEstablecimientoPermanenteProjectionRef(BaseModel):
    """One numbered permanent establishment of a non-resident in the INCN block.

    Numbered from 1 on the SAME sheet as the group-company block above, which is
    why slots are grouped by the block phrase preceding the number rather than
    by sheet.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_incn_establecimiento_permanente"]
    slot: int = Field(ge=1, le=5)


class M200OperacionReestructuracionField(StrEnum):
    """Closed fields of one fusion, escision or canje de valores row."""

    TIPO_OPERACION = "tipo_operacion"
    TRANSMITENTE_NIF = "transmitente_nif"
    TRANSMITENTE_DENOMINACION_SOCIAL = "transmitente_denominacion_social"
    ADQUIRENTE_NIF = "adquirente_nif"
    ADQUIRENTE_DENOMINACION_SOCIAL = "adquirente_denominacion_social"
    FECHA_INSCRIPCION_REGISTRO_MERCANTIL = "fecha_inscripcion_registro_mercantil"
    FECHA_COMUNICACION_OPERACION = "fecha_comunicacion_operacion"
    VALOR_ACCIONES_ENTREGADAS = "valor_acciones_entregadas"
    VALOR_ACCIONES_RECIBIDAS = "valor_acciones_recibidas"
    IMPORTE_RENTAS_NO_INTEGRADAS = "importe_rentas_no_integradas"


class M200OperacionReestructuracionProjectionRef(BaseModel):
    """One numbered restructuring operation row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_operacion_reestructuracion"]
    slot: int = Field(ge=1, le=5)
    field: M200OperacionReestructuracionField


class M200ParticipeAieUteField(StrEnum):
    """Closed fields of one AIE/UTE participe row."""

    NIF = "nif"
    REPRESENTANTE = "representante"
    FORMA_JURIDICA = "forma_juridica"
    RESIDENCIA = "residencia"
    APELLIDOS_NOMBRE_RAZON_SOCIAL = "apellidos_nombre_razon_social"
    CODIGO_PROVINCIA_PAIS = "codigo_provincia_pais"
    BASE_IMPONIBLE = "base_imponible"
    PORCENTAJE_PARTICIPACION = "porcentaje_participacion"


class M200ParticipeAieUteProjectionRef(BaseModel):
    """One numbered participe of an agrupacion de interes economico or UTE."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_participe_aie_ute"]
    slot: int = Field(ge=1, le=10)
    field: M200ParticipeAieUteField


class M200TransparenciaFiscalInternacionalField(StrEnum):
    """Closed fields of one transparencia fiscal internacional entity row."""

    NOMBRE_O_RAZON_SOCIAL = "nombre_o_razon_social"
    DOMICILIO_SOCIAL = "domicilio_social"
    CLAVE_PAIS_TERRITORIO = "clave_pais_territorio"
    IMPORTE_RENTA = "importe_renta"
    ADMINISTRADORES_LINEA_1 = "administradores_linea_1"
    ADMINISTRADORES_LINEA_2 = "administradores_linea_2"
    ADMINISTRADORES_LINEA_3 = "administradores_linea_3"
    ADMINISTRADORES_LINEA_4 = "administradores_linea_4"
    ADMINISTRADORES_LINEA_5 = "administradores_linea_5"


class M200TransparenciaFiscalInternacionalProjectionRef(BaseModel):
    """One numbered entity row of the transparencia fiscal internacional regime.

    AEAT letters each slot's importe -- "Importe renta [A]", "[B]", "[C]" -- which
    is a slot marker rather than a different field, so every slot carries the same
    nine fields.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_transparencia_fiscal_internacional"]
    slot: int = Field(ge=1, le=6)
    field: M200TransparenciaFiscalInternacionalField


class M200AdministradorField(StrEnum):
    """Closed fields of one row of the relacion de administradores."""

    NIF = "nif"
    FORMA_JURIDICA = "forma_juridica"
    REPRESENTANTE = "representante"
    APELLIDOS_NOMBRE_RAZON_SOCIAL = "apellidos_nombre_razon_social"
    DOMICILIO_FISCAL = "domicilio_fiscal"
    CODIGO_PROVINCIA = "codigo_provincia"


class M200AdministradorProjectionRef(BaseModel):
    """One numbered administrador row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_administrador"]
    slot: int = Field(ge=1, le=5)
    field: M200AdministradorField


class M200EntidadParticipadaField(StrEnum):
    """Closed fields of one AIE/UTE participada row.

    Declared in the order AEAT prints them. The Canary-Islands investment
    variants precede their plain counterparts, which is read from the design
    rather than assumed.
    """

    NIF = "nif"
    NOMBRE_O_RAZON_SOCIAL = "nombre_o_razon_social"
    CODIGO_PROVINCIA_PAIS = "codigo_provincia_pais"
    TIPO_AGRUPACION_INTERES_ECONOMICO_ESPANOLA = "tipo_agrupacion_interes_economico_espanola"
    TIPO_AGRUPACION_EUROPEA_INTERES_ECONOMICO = "tipo_agrupacion_europea_interes_economico"
    TIPO_UNION_TEMPORAL_EMPRESAS = "tipo_union_temporal_empresas"
    TIPO_COLABORACION_EXTRANJERA_ANALOGA = "tipo_colaboracion_extranjera_analoga"
    CRITERIO_IMPUTACION_FIN_PERIODO = "criterio_imputacion_fin_periodo"
    CRITERIO_IMPUTACION_SIGUIENTE_PERIODO = "criterio_imputacion_siguiente_periodo"
    VALORACION_PARTICIPACION_INICIO = "valoracion_participacion_inicio"
    VALORACION_PARTICIPACION_FINAL = "valoracion_participacion_final"
    INGRESOS_FINANCIEROS_PARTICIPACION = "ingresos_financieros_participacion"
    RESULTADO_CONTABLE_IMPUTADO = "resultado_contable_imputado"
    GASTOS_FINANCIEROS_NETOS_IMPUTADOS = "gastos_financieros_netos_imputados"
    RESERVA_CAPITALIZACION_NO_APLICADA_IMPUTADA = "reserva_capitalizacion_no_aplicada_imputada"
    BASE_IMPONIBLE_IMPUTADA = "base_imponible_imputada"
    DEDUCCION_DOBLE_IMPOSICION_BASES_IMPUTADAS = "deduccion_doble_imposicion_bases_imputadas"
    BONIFICACION_BASES_IMPUTADAS = "bonificacion_bases_imputadas"
    DEDUCCION_ACTIVOS_FIJOS_CANARIAS = "deduccion_activos_fijos_canarias"
    DEDUCCION_IDI_CANARIAS = "deduccion_idi_canarias"
    DEDUCCION_PRODUCCION_ESPECTACULOS_CANARIAS = "deduccion_produccion_espectaculos_canarias"
    DEDUCCION_RESTO_INVERSION_CANARIAS = "deduccion_resto_inversion_canarias"
    DEDUCCION_IDI_BASES_IMPUTADAS = "deduccion_idi_bases_imputadas"
    DEDUCCION_PRODUCCION_ESPECTACULOS_BASES_IMPUTADAS = "deduccion_produccion_espectaculos_bases_imputadas"
    DEDUCCION_RESTO_INCENTIVAR_ACTIVIDADES = "deduccion_resto_incentivar_actividades"
    DEDUCCION_RESTO_NO_MENCIONADAS = "deduccion_resto_no_mencionadas"
    RETENCIONES_INGRESOS_A_CUENTA_IMPUTADOS = "retenciones_ingresos_a_cuenta_imputados"
    DIVIDENDOS_EJERCICIOS_ANTERIORES = "dividendos_ejercicios_anteriores"
    DIVIDENDOS_EJERCICIOS_POSTERIORES = "dividendos_ejercicios_posteriores"


class M200EntidadParticipadaProjectionRef(BaseModel):
    """One sub-lettered AIE/UTE participada row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_entidad_participada"]
    slot: int = Field(ge=1, le=3)
    field: M200EntidadParticipadaField


class M200ParticipacionDirectaField(StrEnum):
    """Closed fields of one B.1 participacion directa row of the declarante."""

    NIF = "nif"
    NOMBRE_O_RAZON_SOCIAL = "nombre_o_razon_social"
    CODIGO_PROVINCIA_PAIS = "codigo_provincia_pais"
    PORCENTAJE_PARTICIPACION = "porcentaje_participacion"
    VALOR_NOMINAL_TOTAL = "valor_nominal_total"
    VALOR_EN_LIBROS = "valor_en_libros"
    INGRESOS_POR_DIVIDENDOS = "ingresos_por_dividendos"
    CORRECCION_VALOR_PERDIDAS_GANANCIAS = "correccion_valor_perdidas_ganancias"
    REVERSION_PERDIDAS_DETERIORO_VALORES = "reversion_perdidas_deterioro_valores"
    ELIMINACION_DETERIORO_CONTABLE = "eliminacion_deterioro_contable"
    ELIMINACION_DETERIORO_VALORES_PARTICIPACION = "eliminacion_deterioro_valores_participacion"
    AJUSTE_VALOR_RAZONABLE = "ajuste_valor_razonable"
    EFECTO_CORRECCION_VALORATIVA_BASE_IMPONIBLE = "efecto_correccion_valorativa_base_imponible"
    SALDO_CORRECCIONES_FISCALES_PENDIENTES = "saldo_correcciones_fiscales_pendientes"
    CAPITAL = "capital"
    RESERVAS_Y_OTRAS_PARTIDAS_FONDOS_PROPIOS = "reservas_y_otras_partidas_fondos_propios"
    OTRAS_PARTIDAS_PATRIMONIO_NETO = "otras_partidas_patrimonio_neto"
    RESULTADO_ULTIMO_EJERCICIO = "resultado_ultimo_ejercicio"


class M200ParticipacionDirectaProjectionRef(BaseModel):
    """One numbered B.1 participacion of the declarante in another entity."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_participacion_directa"]
    slot: int = Field(ge=1, le=3)
    field: M200ParticipacionDirectaField


class M200ParticipacionSocioField(StrEnum):
    """Closed fields of one B.2 row: a person or entity holding the declarante."""

    NIF = "nif"
    REPRESENTANTE = "representante"
    FORMA_JURIDICA = "forma_juridica"
    APELLIDOS_NOMBRE_RAZON_SOCIAL = "apellidos_nombre_razon_social"
    CODIGO_PROVINCIA_PAIS = "codigo_provincia_pais"
    NOMINAL = "nominal"
    PORCENTAJE_PARTICIPACION = "porcentaje_participacion"


class M200ParticipacionSocioProjectionRef(BaseModel):
    """One B.2 holder row.

    AEAT prints no index here; the row identity comes from the field labels
    restarting at "N.I.F." every seventh field.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_participacion_socio"]
    slot: int = Field(ge=1, le=6)
    field: M200ParticipacionSocioField


class M200SecretarioConsejoField(StrEnum):
    """Closed fields of the secretario del consejo de administracion row."""

    APELLIDOS_Y_NOMBRE = "apellidos_y_nombre"
    NIF = "nif"


class M200SecretarioConsejoProjectionRef(BaseModel):
    """The secretario del consejo de administracion.

    Exactly one slot: the design's section G prints a single secretario, then a
    separately-shaped list of representantes legales, which is its own
    projection rather than a further slot of this one.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_secretario_consejo"]
    slot: int = Field(ge=1, le=1)
    field: M200SecretarioConsejoField


class M200RepresentanteLegalField(StrEnum):
    """Closed fields of one representante legal row.

    Wider than the secretario's: AEAT prints a fecha de poder and a notaria for
    a representante and neither for the secretario, so the two cannot share one
    field set without one of them declaring slots it can never fill.
    """

    APELLIDOS_Y_NOMBRE = "apellidos_y_nombre"
    NIF = "nif"
    FECHA_PODER = "fecha_poder"
    NOTARIA_OTROS = "notaria_otros"


class M200RepresentanteLegalProjectionRef(BaseModel):
    """One representante legal de la entidad row."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m200_representante_legal"]
    slot: int = Field(ge=1, le=3)
    field: M200RepresentanteLegalField


class M296PerceptorField(StrEnum):
    """Closed fields of one Modelo 296 perceptor row.

    Modelo 296 is the IRNR annual withholding summary, and AEAT repeats the whole
    PERCEPTOR RECORD once per payee rather than repeating fields inside one record. The
    row's data already exists in the registry as
    :class:`~cadrumo.domain.calculations.registry.Withholding296Observation` -- perceptor
    tax id, legal name, naturaleza, clave, subclave, base and retención -- so these fields
    are projected from that observation set rather than supplied as operator header facts.

    Declaring them as header producers is what left every one of them rendering blank on a
    filed 296 while the withholding substrate already held the values.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    BASE_RETENCIONES_E_INGRESOS_A_CUENTA = "base_retenciones_e_ingresos_a_cuenta"
    CIUDAD = "ciudad"
    CLAVE = "clave"
    CLAVE_DE_MERCADO = "clave_de_mercado"
    CODIGO = "codigo"
    CODIGO_BIC_DEL_PERCEPTOR_MEDIADOR = "codigo_bic_del_perceptor_mediador"
    CODIGO_CUENTA_VALORES = "codigo_cuenta_valores"
    CODIGO_EMISOR = "codigo_emisor"
    CODIGO_LEI_DEL_PERCEPTOR = "codigo_lei_del_perceptor"
    CODIGO_PAIS = "codigo_pais"
    DECIMAL = "decimal"
    DECIMAL_NUMERICO_PARTE_DECIMAL = "decimal_numerico_parte_decimal"
    DECIMAL_NUMERICO_PARTE_DECIMAL_2 = "decimal_numerico_parte_decimal_2"
    DECIMAL_NUMERICO_PARTE_DECIMAL_3 = "decimal_numerico_parte_decimal_3"
    DECLARANTE = "declarante"
    DIRECCION_DEL_PERCEPTOR = "direccion_del_perceptor"
    EJERCICIO = "ejercicio"
    EJERCICIO_DEVENGO = "ejercicio_devengo"
    ENTERO = "entero"
    ENTERO_NUMERICO_PARTE_ENTERA = "entero_numerico_parte_entera"
    ENTERO_NUMERICO_PARTE_ENTERA_2 = "entero_numerico_parte_entera_2"
    ENTERO_NUMERICO_PARTE_ENTERA_3 = "entero_numerico_parte_entera_3"
    F_J = "f_j"
    FECHA_DE_DEVENGO = "fecha_de_devengo"
    FECHA_DE_INICIO_DEL_PRESTAMO = "fecha_de_inicio_del_prestamo"
    FECHA_DE_NACIMIENTO = "fecha_de_nacimiento"
    FECHA_DE_VENCIMIENTO_DEL_PRESTAMO = "fecha_de_vencimiento_del_prestamo"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    INGRESOS_A_CUENTA_REPERCUTIDOS = "ingresos_a_cuenta_repercutidos"
    NATURALEZA = "naturaleza"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PAGADOR_ANTERIOR = "nif_del_pagador_anterior"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL = "nif_en_el_pais_de_residencia_fiscal"
    PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "pais_o_territorio_de_residencia_fiscal"
    PARTE_DECIMAL_DEL_IMPORTE_DE_LAS_RETEN = "parte_decimal_del_importe_de_las_reten"
    PARTE_ENTERA_DEL_IMPORTE_DE_LAS_RETENC = "parte_entera_del_importe_de_las_retenc"
    PENDIENTE = "pendiente"
    PERCEPTOR_MEDIADOR = "perceptor_mediador"
    PROCEDIMIENTO_ESPECIAL_DE_RETENCIONES = "procedimiento_especial_de_retenciones"
    SUBCLAVE = "subclave"
    TIPO_CODIGO = "tipo_codigo"


class M296PerceptorProjectionRef(BaseModel):
    """One field of the Modelo 296 perceptor row.

    This reference carries NO slot, and the omission is the point. The m200 party
    references carry one because AEAT prints those rows a fixed number of times on the
    form, so the slot is part of the field's address. The number of perceptores is the
    number of payees and is not bounded by the design, so the perceptor RECORD repeats
    instead: it declares ``repeat = "projection_rows"``, the plan emits one render context
    per payee, and the projection address is completed by that context's occurrence. A
    slot here would be a second row axis that is always 1 -- meaningless at best, and at
    worst an invitation to cap the payees at the slots someone declared.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_perceptor"]
    field: M296PerceptorField


class M296PerceptorInteresesField(StrEnum):
    """Closed fields of one Modelo 296 perceptor-intereses row.

    AEAT's alternative Tipo 2 hoja (TIPO DE HOJA ``F``) for intereses y otras rentas,
    emitted once per perceptor of that type. Its single payload field is the aggregate
    of retenciones ingresadas across the Estado, the Diputaciones Forales del Pais
    Vasco and the Comunidad Foral de Navarra.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    EJERCICIO = "ejercicio"
    F_J = "f_j"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    RETENCIONES_E_INGRESOS_A_CUENTA_INGRES = "retenciones_e_ingresos_a_cuenta_ingres"


class M296PerceptorInteresesProjectionRef(BaseModel):
    """One field of a Modelo 296 perceptor-intereses row.

    No slot: the record repeats and the render occurrence identifies the perceptor.
    See :class:`M296PerceptorProjectionRef` for why that is the right axis here.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_perceptor_intereses"]
    field: M296PerceptorInteresesField


class M296AnexoPagoField(StrEnum):
    """Closed fields of one Modelo 296 anexo A row: a pago to one contribuyente.

    AEAT's "Anexo - Valores Negociables. Relacion de Pago a Contribuyentes" is a
    relacion -- a list -- and each row carries its own ISIN, fecha de devengo,
    contribuyente identity, importe, porcentaje and retenciones, beneath perceptor
    header fields that AEAT restates on every row.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "apellidos_y_nombre_razon_social_o_deno_2"
    CIUDAD = "ciudad"
    CLAVE_DE_PERSONALIDAD_DEL_CONTRIBUYENT = "clave_de_personalidad_del_contribuyent"
    CODIGO_ISIN = "codigo_isin"
    CODIGO_LEI_DEL_CONTRIBUYENTE = "codigo_lei_del_contribuyente"
    CODIGO_PAIS = "codigo_pais"
    DIRECCION_DEL_CONTRIBUYENTE = "direccion_del_contribuyente"
    EJERCICIO = "ejercicio"
    F_J = "f_j"
    FECHA_DE_DEVENGO = "fecha_de_devengo"
    FECHA_DE_NACIMIENTO_DEL_CONTRIBUYENTE = "fecha_de_nacimiento_del_contribuyente"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    IMPORTE_DEL_PAGO_AL_CONTRIBUYENTE = "importe_del_pago_al_contribuyente"
    NIF_DEL_CONTRIBUYENTE = "nif_del_contribuyente"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NIF_EN_EL_PAIS_DE_RESIDENCIA_FISCAL_DE = "nif_en_el_pais_de_residencia_fiscal_de"
    NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "numero_de_justificante_del_modelo_210"
    PAIS_O_TERRITORIO_DE_RESIDENCIA_FISCAL = "pais_o_territorio_de_residencia_fiscal"
    PORCENTAJE_DE_RETENCION = "porcentaje_de_retencion"
    RETENCIONES = "retenciones"


class M296AnexoPagoProjectionRef(BaseModel):
    """One field of a Modelo 296 anexo A pago row.

    No slot: the record repeats once per pago and the render occurrence identifies it.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_anexo_pago"]
    field: M296AnexoPagoField


class M296AnexoCertificadoField(StrEnum):
    """Closed fields of one Modelo 296 anexo B row: one certificado de pago.

    AEAT's "Anexo - Valores Negociables. Relacion de Certificados de Pago" is a
    relacion, one row per certificado, each carrying its ISIN, codigo cuenta de
    valores, titular registral, numero de titulos, fecha de pago, importe bruto and
    retencion.

    Several member names are opaque -- ``entero``, ``decimal``, ``entero_2`` and their
    siblings -- because AEAT's design splits a money field into entera and decimal
    sub-columns and the source slug took the sub-column heading rather than the parent
    field name. The parent each belongs to is recorded on the member.
    """

    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO = "apellidos_y_nombre_razon_social_o_deno"
    APELLIDOS_Y_NOMBRE_RAZON_SOCIAL_O_DENO_2 = "apellidos_y_nombre_razon_social_o_deno_2"
    CODIGO_CUENTA_VALORES_DEL_CERTIFICADO = "codigo_cuenta_valores_del_certificado"
    CODIGO_ISIN_DEL_CERTIFICADO = "codigo_isin_del_certificado"
    CODIGO_LEI_DEL_TITULAR_REGISTRAL = "codigo_lei_del_titular_registral"
    #: IMPORTE BRUTO DE LA RENTA DEL CERTIFICADO, decimal.
    DECIMAL = "decimal"
    #: RETENCION DEL CERTIFICADO, decimal.
    DECIMAL_2 = "decimal_2"
    #: PORCENTAJE DE RETENCION DEL CERTIFICADO, decimal.
    DECIMAL_3 = "decimal_3"
    EJERCICIO = "ejercicio"
    #: IMPORTE BRUTO DE LA RENTA DEL CERTIFICADO, entera.
    ENTERO = "entero"
    #: RETENCION DEL CERTIFICADO, entera.
    ENTERO_2 = "entero_2"
    #: PORCENTAJE DE RETENCION DEL CERTIFICADO, entera.
    ENTERO_3 = "entero_3"
    F_J = "f_j"
    FECHA_DE_PAGO = "fecha_de_pago"
    FECHA_DE_PRESENTACION_DEL_MODELO_210 = "fecha_de_presentacion_del_modelo_210"
    IDENTIFICADOR_DE_REGISTRO_O_NUMERO_DE = "identificador_de_registro_o_numero_de"
    NIF_DEL_DECLARANTE = "nif_del_declarante"
    NIF_DEL_PERCEPTOR = "nif_del_perceptor"
    NIF_DEL_REPRESENTANTE_LEGAL = "nif_del_representante_legal"
    NUMERO_DE_JUSTIFICANTE_DEL_MODELO_210 = "numero_de_justificante_del_modelo_210"
    #: NUMERO DE TITULOS EN LA CUENTA DE VALORES, decimal.
    PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS = "parte_decimal_del_numero_de_titulos"
    #: NUMERO DE TITULOS DEL CONTRIBUYENTE, decimal.
    PARTE_DECIMAL_DEL_NUMERO_DE_TITULOS_2 = "parte_decimal_del_numero_de_titulos_2"
    #: NUMERO DE TITULOS EN LA CUENTA DE VALORES, entera.
    PARTE_ENTERA_DEL_NUMERO_DE_TITULOS = "parte_entera_del_numero_de_titulos"
    #: NUMERO DE TITULOS DEL CONTRIBUYENTE, entera.
    PARTE_ENTERA_DEL_NUMERO_DE_TITULOS_2 = "parte_entera_del_numero_de_titulos_2"
    TITULAR_REGISTRAL_DE_LA_CUENTA_DE_VALO = "titular_registral_de_la_cuenta_de_valo"


class M296AnexoCertificadoProjectionRef(BaseModel):
    """One field of a Modelo 296 anexo B certificado row.

    No slot: the record repeats once per certificado and the occurrence identifies it.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m296_anexo_certificado"]
    field: M296AnexoCertificadoField


FilingProjectionRef = Annotated[
    M303ProrrataActivityProjectionRef
    | M303DifferentiatedDeductionProjectionRef
    | M303RegimenSimplificadoActivityProjectionRef
    | M303RegimenSimplificadoFactProjectionRef
    | M303RegimenSimplificadoModuleProjectionRef
    | M303Exonerado390ActivityProjectionRef
    | M303Exonerado390OperacionesTercerosProjectionRef
    | M390ActivityProjectionRef
    | M390RepresentativeProjectionRef
    | M390RegimenSimplificadoActivityProjectionRef
    | M390RegimenSimplificadoModuleProjectionRef
    | M390ProrrataActivityProjectionRef
    | M390DifferentiatedDeductionProjectionRef
    | M200EstablecimientoPermanenteProjectionRef
    | M200SocioSicavDisolucionProjectionRef
    | M200EntidadMenorDependienteProjectionRef
    | M200IncnGrupoSociedadProjectionRef
    | M200IncnEstablecimientoPermanenteProjectionRef
    | M200OperacionReestructuracionProjectionRef
    | M200ParticipeAieUteProjectionRef
    | M200TransparenciaFiscalInternacionalProjectionRef
    | M200AdministradorProjectionRef
    | M200EntidadParticipadaProjectionRef
    | M200ParticipacionDirectaProjectionRef
    | M200ParticipacionSocioProjectionRef
    | M200SecretarioConsejoProjectionRef
    | M200RepresentanteLegalProjectionRef
    | M296PerceptorProjectionRef
    | M296PerceptorInteresesProjectionRef
    | M296AnexoPagoProjectionRef
    | M296AnexoCertificadoProjectionRef,
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
        "representative_kind",
        "value",
    },
)


def _validated_type_members(union_args: tuple[object, ...]) -> tuple[type, ...]:
    """Return ``union_args`` re-typed as ``type``, refusing a non-class member."""
    validated: list[type] = []
    for member in union_args:
        if not isinstance(member, type):
            raise TypeError(f"expected a FilingProjectionRef union member to be a type, got {member!r}")
        validated.append(member)
    return tuple(validated)


#: The typed members a compiled projection reference can be. Derived from the
#: annotated union rather than restated, so a new member cannot be forgotten
#: here: ``get_args`` on the Annotated alias yields the union first, whose own
#: args are the member classes.
_TYPED_FILING_PROJECTION_REFS: Final[tuple[type, ...]] = _validated_type_members(
    get_args(get_args(FilingProjectionRef)[0]),
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
        # An explicit JSON null means the optional field is absent. Serialising a
        # reference emits every declared field, so a round-tripped payload states
        # `sub_index: null` where the model's own default is None; refusing that
        # would refuse a value the target model accepts, and would make a
        # reference unable to survive its own serialisation. A null on a REQUIRED
        # field still refuses, because dropping it leaves the field missing.
        if raw_value is None:
            continue
        # A python-mode ``model_dump()`` emits StrEnum MEMBERS, and the
        # exact-type checks below reject one although a member's value IS the
        # wire primitive -- which made every layout carrying a projection
        # unable to survive its own serialisation. Narrowing to the value keeps
        # those checks strict against genuine non-primitives (a bool still
        # refuses on an integer field) for the same reason the null branch
        # above exists: refusing a value the target model accepts is a defect,
        # not strictness.
        payload[raw_key] = raw_value.value if isinstance(raw_value, StrEnum) else raw_value
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


def hydrate_filing_projection_ref(value: object) -> FilingProjectionRef:
    """Return ``value`` as a typed reference, compiling it if it is still raw.

    The one entry point every persisted boundary uses. A reference that is
    already typed was produced by :func:`compile_filing_projection_ref` and is
    returned unchanged; a mapping is compiled by that same function now. So the
    invariant is "every projection reference was compiled by the one canonical
    compiler", which is what the boundaries actually need to guarantee.

    Boundaries previously asserted that invariant by demanding an
    already-constructed model. That proxy held for TOML, where the loader
    compiles before validating, and was impossible for JSON, where a reference
    can only arrive as a mapping -- so a manifest could be written and never
    read back. Compiling here reaches the same guarantee through one path
    instead of one path and one dead end, and a malformed mapping still refuses
    exactly as it always did, because the compiler is unchanged.
    """
    if isinstance(value, _TYPED_FILING_PROJECTION_REFS):
        return cast(FilingProjectionRef, value)
    return compile_filing_projection_ref(value)


def filing_projection_ref_casilla_id(reference: FilingProjectionRef) -> CasillaId | None:
    """Return the numbered official endpoint carried by ``reference``, if any."""
    if isinstance(reference, M303ProrrataActivityProjectionRef | M303DifferentiatedDeductionProjectionRef):
        return reference.casilla_id
    return None


__all__ = [
    "FilingProjectionRef",
    "M200AdministradorField",
    "M200AdministradorProjectionRef",
    "M200EntidadMenorDependienteField",
    "M200EntidadMenorDependienteProjectionRef",
    "M200EntidadParticipadaField",
    "M200EntidadParticipadaProjectionRef",
    "M200EstablecimientoPermanenteField",
    "M200EstablecimientoPermanenteProjectionRef",
    "M200IncnEstablecimientoPermanenteProjectionRef",
    "M200IncnGrupoSociedadField",
    "M200IncnGrupoSociedadProjectionRef",
    "M200OperacionReestructuracionField",
    "M200OperacionReestructuracionProjectionRef",
    "M200ParticipacionDirectaField",
    "M200ParticipacionDirectaProjectionRef",
    "M200ParticipacionSocioField",
    "M200ParticipacionSocioProjectionRef",
    "M200ParticipeAieUteField",
    "M200ParticipeAieUteProjectionRef",
    "M200RepresentanteLegalField",
    "M200RepresentanteLegalProjectionRef",
    "M200SecretarioConsejoField",
    "M200SecretarioConsejoProjectionRef",
    "M200SocioSicavDisolucionField",
    "M200SocioSicavDisolucionProjectionRef",
    "M200TransparenciaFiscalInternacionalField",
    "M200TransparenciaFiscalInternacionalProjectionRef",
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
    "M390ActivityField",
    "M390ActivityProjectionRef",
    "M390DifferentiatedDeductionProjectionField",
    "M390DifferentiatedDeductionProjectionRef",
    "M390ProrrataActivityProjectionField",
    "M390ProrrataActivityProjectionRef",
    "M390RegimenSimplificadoActivityField",
    "M390RegimenSimplificadoActivityProjectionRef",
    "M390RegimenSimplificadoCohort",
    "M390RegimenSimplificadoModuleProjectionRef",
    "M390RegimenSimplificadoModuleValue",
    "M390RepresentativeField",
    "M390RepresentativeKind",
    "M390RepresentativeProjectionRef",
    "compile_filing_projection_ref",
    "filing_projection_ref_casilla_id",
    "hydrate_filing_projection_ref",
]
