"""Withholding row-set binding helpers.

Withholding-source bindings declared on a :class:`ModeloRevision` are resolved
from per-perceptor withholding observations into scalar values or row outputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, TypeAdapter, ValidationError, field_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind, RetencionClave
from ....core.country_code import CountryCodeAlpha2
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.percentage import PERCENTAGE_MIN, Percentage
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
    optional_uppercase_alpha_code,
    unique_tuple,
)
from .binding_selector_utils import (
    selector_as_dict as _selector_as_dict,
)
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision

__all__ = [
    "WithholdingClaveBreakdown",
    "WithholdingObservation",
    "WithholdingObservationRequirement",
    "WithholdingTotalsParity",
    "aggregate_withholding_by_clave",
    "compute_withholding_totals_parity",
    "resolve_withholding_binding_row_values",
    "resolve_withholding_binding_values",
    "validate_withholding_binding_selector_shape",
    "withholding_binding_requirements",
]

_WithholdingRowField = Literal[
    "perceptor_tax_id",
    "perceptor_legal_name",
    "country_code",
    "province_code",
    "territorial_deduction_clave",
    "perceptor_birth_year",
    "perceptor_situacion_familiar",
    "representative_tax_id",
    "spouse_or_unit_titular_tax_id",
    "disability_clave",
    "contract_relation_clave",
    "unit_convivencia_titular_clave",
    "geographic_mobility_clave",
    "clave",
    "subclave",
    "percibido_dinerario",
    "percibido_especie",
    "retencion_practicada",
    "ingreso_a_cuenta",
    "ingreso_a_cuenta_repercutido",
    "accrual_year",
    "reducciones_aplicables",
    "gastos_deducibles",
    "pension_compensatoria",
    "anualidades_alimentos",
    "descendants_under_3_total",
    "descendants_under_3_whole",
    "descendants_rest_total",
    "descendants_rest_whole",
    "descendants_disabled_33_65_total",
    "descendants_disabled_33_65_whole",
    "descendants_disabled_mobility_total",
    "descendants_disabled_mobility_whole",
    "descendants_disabled_65_plus_total",
    "descendants_disabled_65_plus_whole",
    "ascendants_under_75_total",
    "ascendants_under_75_whole",
    "ascendants_75_plus_total",
    "ascendants_75_plus_whole",
    "ascendants_disabled_33_65_total",
    "ascendants_disabled_33_65_whole",
    "ascendants_disabled_mobility_total",
    "ascendants_disabled_mobility_whole",
    "ascendants_disabled_65_plus_total",
    "ascendants_disabled_65_plus_whole",
    "first_child_compute",
    "second_child_compute",
    "third_child_compute",
    "housing_loan_communication_clave",
    "incapacity_cash_perception",
    "incapacity_cash_withholding",
    "incapacity_kind_value",
    "incapacity_kind_ingreso_a_cuenta",
    "incapacity_kind_repercutido",
    "complemento_infancia_clave",
    "foral_retention_estatal",
    "foral_retention_navarra",
    "foral_retention_araba",
    "foral_retention_gipuzkoa",
    "foral_retention_bizkaia",
    "emerging_stock_excess_clave",
    "startup_fund_rendimientos_clave",
    "pension_prestacion_jubilacion",
    "pension_prestacion_viudedad",
    "pension_prestacion_incapacidad",
    "pension_prestacion_no_contributiva",
    "pension_prestacion_resto",
    "perceptor_mediador_flag",
    "clave_codigo",
    "codigo_emisor",
    "naturaleza",
    "pago",
    "tipo_codigo",
    "codigo_cuenta",
    "pendiente_flag",
    "tipo_percepcion",
    "reducciones",
    "base_retenciones",
    "porcentaje_retencion",
    "penalizaciones",
    "isin_code",
    "naturaleza_declarante",
    "fecha_inicio_prestamo",
    "fecha_vencimiento_prestamo",
    "compensaciones",
    "garantias",
    "nif_pagador_anterior",
    "fecha_devengo",
    "clave_mercado",
    "numero_orden",
]
_WithholdingGrouping = Literal["per_perceptor", "per_perceptor_clave"]
_WITHHOLDING_FACTS = frozenset(
    {
        "row_field",
        "perceptor_count",
        "percepcion_count",
        "percibido_sum",
        "retencion_sum",
        "retenciones_ingresadas_sum",
    },
)
_WithholdingFact = Literal[
    "row_field",
    "perceptor_count",
    "percepcion_count",
    "percibido_sum",
    "retencion_sum",
    "retenciones_ingresadas_sum",
]
_CLAVE_TOKEN_SEQUENCE_ADAPTER: TypeAdapter[list[object] | tuple[object, ...]] = TypeAdapter(
    list[object] | tuple[object, ...], config=ConfigDict(strict=True)
)


class WithholdingObservation(BaseModel):
    """Per-perceptor retencion / ingreso-a-cuenta observation for modelo 190 / 193.

    ``perceptor_tax_id`` is normalised to its canonical identity token on
    construction, so the identity the clave/subclave aggregations count is the
    identity the encrypted percepciones store keys by. Holding the raw
    declaration here split the two: the repository trimmed and uppercased the
    tax ID before hashing it into the object key, so two canonically-equal
    declarations were counted as two distinct percepciones while sharing one
    stored row, and the later write overwrote the earlier evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    perceptor_tax_id: TaxIdIdentityToken = Field(min_length=1, max_length=64)
    perceptor_legal_name: str = Field(default="", max_length=200)
    country_code: CountryCodeAlpha2 | None = None
    """The party's country, or ``None`` when the source stated none.

    Nullable rather than defaulted to ``ES``, because these forms carry the
    NON-RESIDENT population by construction -- a perceptor on a withholding
    form is routinely foreign, and an attribution member can be -- so a
    default silently declares a foreign party Spanish on a filing surface.

    Absence propagates as an ABSENT KEY in the built row rather than as a
    value, so a binding that needs the country refuses with the shipped
    not-produced error naming itself. That is the visible failure the silent
    default replaced."""
    transaction_date: date
    clave: RetencionClave
    subclave: str = Field(default="", max_length=4, pattern=r"^[0-9]*$")
    percibido_dinerario: Decimal = Decimal("0")
    """The NON-incapacidad part of the row's dineraria percepciones: the design's
    campo 11 excludes the incapacidad-laboral prestaciones, which file in their
    own block (255-281), so the operator records them in the incap facts."""
    percibido_especie: Decimal = Decimal("0")
    retencion_practicada: Decimal = Decimal("0")
    ingreso_a_cuenta: Decimal = Decimal("0")
    province_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    """Perceptor domicilio province code (01-52, 53 La Palma), or 98 for a Spanish IRPF
    contributor resident abroad, per the Modelo 190 record design's own list.

    Nullable rather than defaulted: the design's 98 special case makes a default
    province a fabricated residence. Absence propagates as an ABSENT KEY in the
    built row, so a binding that needs the province refuses with the shipped
    not-produced error naming itself."""
    territorial_deduction_clave: int | None = Field(default=None, ge=0, le=2)
    """Modelo 190 CEUTA O MELILLA clave: 1 when the payer applied the art. 68.4
    deduction for Ceuta/Melilla rentas, 2 for the Isla de La Palma exceptional
    deduction, 0 otherwise. A retention-rate determination fact the payer's own
    data carries; never derived from the province code."""
    perceptor_birth_year: int | None = Field(default=None, ge=1900, le=2100)
    """Perceptor birth year, only declared by the design for claves A, B (subclaves
    01, 03, 04, 99) and C."""
    perceptor_situacion_familiar: int | None = Field(default=None, ge=1, le=3)
    """Perceptor family-situation clave (1-3) per the design's own relation, only
    declared for claves A, B (subclaves 01, 03, 04, 99) and C."""
    representative_tax_id: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    """NIF of the perceptor's legal representative, declared by the design only when
    the perceptor is under 14; every other row writes the design's own spaces."""
    spouse_or_unit_titular_tax_id: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    """NIF of the perceptor's spouse (situacion familiar 2, claves A/B/C) or of the
    unidad de convivencia's titular (clave L.29 with titular clave 2); spaces elsewhere."""
    disability_clave: int | None = Field(default=None, ge=0, le=3)
    """Perceptor disability degree clave (0 none/<33%, 1 33-65%, 2 33-65% needing
    third-party help or reduced mobility, 3 >=65%), declared for claves A, B
    (subclaves 01, 03, 04, 99) and C."""
    contract_relation_clave: int | None = Field(default=None, ge=1, le=4)
    """Contract-or-relation type clave (1 general, 2 under-a-year/artists, 3 other
    special dependent relations, 4 sporadic peonadas), declared for clave A only."""
    unit_convivencia_titular_clave: int | None = Field(default=None, ge=1, le=2)
    """Whether the perceptor is the unidad de convivencia's titular (1 yes, 2 no),
    declared for clave L.29 only."""
    geographic_mobility_clave: int | None = Field(default=None, ge=0, le=1)
    """Art. 19.2.f) geographic-mobility deduction flag (1 entitled, 0 not),
    declared for clave A only."""
    ingreso_a_cuenta_repercutido: Decimal = Decimal("0")
    """Ingresos a cuenta efectuados on non-incapacidad especie payments that the
    payer repercutido to the perceptor (design positions 135-147)."""
    accrual_year: int | None = Field(default=None, ge=1900, le=2100)
    """Ejercicio de devengo (design positions 148-151), declared only for atrasos
    devengados in earlier exercises or reintegros of earlier-exercise amounts;
    every other row writes the design's own zeros."""
    reducciones_aplicables: Decimal = Decimal("0")
    """Art. 18.2/18.3, DT 11/12 and art. 32.1 reductions the payer actually
    considered (design positions 171-183); the design's own zeros when none."""
    gastos_deducibles: Decimal = Decimal("0")
    """Art. 19.2 a)-c) deductible expenses the payer considered to determine the
    retention rate (design positions 184-196); the design's own zeros when none."""
    pension_compensatoria: Decimal = Decimal("0")
    """Annual compensatory pension to the spouse by judicial resolution (design
    positions 197-209); the design's own zeros when none."""
    anualidades_alimentos: Decimal = Decimal("0")
    """Annual food annuities to children by judicial decision (design positions
    210-222); the design's own zeros when none."""
    descendants_under_3_total: int | None = Field(default=None, ge=0, le=9)
    """Descendants under 3 (design position 223), counted per art. 58 mínimo por
    descendientes rules; the design's own zero when none."""
    descendants_under_3_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-223 descendants, those computed por entero (design 224)."""
    descendants_rest_total: int | None = Field(default=None, ge=0, le=99)
    """Remaining descendants (design positions 225-226)."""
    descendants_rest_whole: int | None = Field(default=None, ge=0, le=99)
    """Of the position 225-226 descendants, those computed por entero (227-228)."""
    descendants_disabled_33_65_total: int | None = Field(default=None, ge=0, le=99)
    """Disabled descendants 33-65% (design positions 229-230, art. 60.2)."""
    descendants_disabled_33_65_whole: int | None = Field(default=None, ge=0, le=99)
    """Of the 229-230 descendants, those computed por entero (231-232)."""
    descendants_disabled_mobility_total: int | None = Field(default=None, ge=0, le=99)
    """Disabled 33-65% descendants with reduced mobility or third-party help need
    (design positions 233-234)."""
    descendants_disabled_mobility_whole: int | None = Field(default=None, ge=0, le=99)
    """Of the 233-234 descendants, those computed por entero (235-236)."""
    descendants_disabled_65_plus_total: int | None = Field(default=None, ge=0, le=99)
    """Disabled descendants at 65% or more (design positions 237-238)."""
    descendants_disabled_65_plus_whole: int | None = Field(default=None, ge=0, le=99)
    """Of the 237-238 descendants, those computed por entero (239-240)."""
    ascendants_under_75_total: int | None = Field(default=None, ge=0, le=9)
    """Ascendants under 75 (design position 241, art. 59)."""
    ascendants_under_75_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-241 ascendants, those computed por entero (242)."""
    ascendants_75_plus_total: int | None = Field(default=None, ge=0, le=9)
    """Ascendants at 75 or more (design position 243)."""
    ascendants_75_plus_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-243 ascendants, those computed por entero (244)."""
    ascendants_disabled_33_65_total: int | None = Field(default=None, ge=0, le=9)
    """Disabled ascendants 33-65% (design position 245)."""
    ascendants_disabled_33_65_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-245 ascendants, those computed por entero (246)."""
    ascendants_disabled_mobility_total: int | None = Field(default=None, ge=0, le=9)
    """Disabled 33-65% ascendants with reduced mobility or third-party help need
    (design position 247)."""
    ascendants_disabled_mobility_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-247 ascendants, those computed por entero (248)."""
    ascendants_disabled_65_plus_total: int | None = Field(default=None, ge=0, le=9)
    """Disabled ascendants at 65% or more (design position 249)."""
    ascendants_disabled_65_plus_whole: int | None = Field(default=None, ge=0, le=9)
    """Of the position-249 ascendants, those computed por entero (250)."""
    first_child_compute: int | None = Field(default=None, ge=1, le=2)
    """How the first child was computed for the retention rate (design position
    251): 1 por entero, 2 por mitad."""
    second_child_compute: int | None = Field(default=None, ge=1, le=2)
    """How the second child was computed (design position 252)."""
    third_child_compute: int | None = Field(default=None, ge=1, le=2)
    """How the third child was computed (design position 253)."""
    housing_loan_communication_clave: int | None = Field(default=None, ge=0, le=1)
    """Whether the perceptor communicated vivienda-habitual loan amounts at some
    point in the exercise (design position 254, art. 86.1 RIRPF last paragraph):
    clave 0 never applied, 1 applied -- both are recorded facts, never defaults."""
    incapacity_cash_perception: Decimal = Decimal("0")
    """Dineraria incapacidad-laboral percepciones paid directly by the payer
    (design positions 256-268); the design's own zeros when none."""
    incapacity_cash_withholding: Decimal = Decimal("0")
    """Retentions on the position-256 percepciones (design positions 269-281);
    the design's own zeros when none -- a perceptor who suffered no retention
    carries zeros by the design's own rule."""
    incapacity_kind_value: Decimal = Decimal("0")
    """Valoracion of in-kind incapacidad-laboral prestaciones under art. 43
    (design positions 283-295); the design's own zeros when none."""
    incapacity_kind_ingreso_a_cuenta: Decimal = Decimal("0")
    """Ingresos a cuenta efectuados on the position-283 prestaciones (design
    positions 296-308); the design's own zeros when none."""
    incapacity_kind_repercutido: Decimal = Decimal("0")
    """The part of the position-296 ingresos a cuenta repercutido to the
    perceptor (design positions 309-321); the design's own zeros when none."""
    complemento_infancia_clave: int | None = Field(default=None, ge=1, le=2)
    """Whether any mensualidad of the L.29 prestacion included the IMV complemento
    de ayuda para la infancia (design position 322): clave 1 included, 2 not --
    both are recorded facts, never defaults."""
    foral_retention_estatal: Decimal = Decimal("0")
    """Clave E retentions and ingresos a cuenta ingresados to the Hacienda Estatal
    (design positions 323-335); the design's own zeros when none."""
    foral_retention_navarra: Decimal = Decimal("0")
    """Clave E retentions and ingresos a cuenta ingresados to the Comunidad Foral
    de Navarra (design positions 336-348); the design's own zeros when none."""
    foral_retention_araba: Decimal = Decimal("0")
    """Clave E retentions and ingresos a cuenta ingresados to the Diputacion Foral
    de Araba/Alava (design positions 349-361); the design's own zeros when none."""
    foral_retention_gipuzkoa: Decimal = Decimal("0")
    """Clave E retentions and ingresos a cuenta ingresados to the Diputacion Foral
    de Gipuzkoa (design positions 362-374); the design's own zeros when none."""
    foral_retention_bizkaia: Decimal = Decimal("0")
    """Clave E retentions and ingresos a cuenta ingresados to the Diputacion Foral
    de Bizkaia (design positions 375-387); the design's own zeros when none."""
    emerging_stock_excess_clave: int | None = Field(default=None, ge=0, le=1)
    """Whether the row's in-kind percepciones include emerging-company stock over
    the art. 42.3.f) exempt amount (design position 388): clave 1 yes, 0 the rest
    of the in-kind retributions -- both recorded facts, declared only for clave A
    and only when the especie block has content."""
    startup_fund_rendimientos_clave: int | None = Field(default=None, ge=0, le=1)
    """Whether the row's payments include D.A. 53a fund-management rendimientos
    del trabajo (2025-edition design position 389): clave 1 yes, 0 the rest. The
    cumplimentacion trigger is the payer's own composition judgment, so the clave
    is recorded-when-applicable: spaces when absent, refused outside clave A."""
    pension_prestacion_jubilacion: int | None = Field(default=None, ge=0, le=1)
    """Whether the clave B.01 prestaciones include jubilacion (2025-edition
    design position 390): each type's 0/1 flag is always recorded for B.01."""
    pension_prestacion_viudedad: int | None = Field(default=None, ge=0, le=1)
    """Whether the clave B.01 prestaciones include viudedad (position 391)."""
    pension_prestacion_incapacidad: int | None = Field(default=None, ge=0, le=1)
    """Whether the clave B.01 prestaciones include incapacidad permanente total o
    parcial (position 392)."""
    pension_prestacion_no_contributiva: int | None = Field(default=None, ge=0, le=1)
    """Whether the clave B.01 prestaciones include pensiones no contributivas por
    invalidez o jubilacion (position 393)."""
    pension_prestacion_resto: int | None = Field(default=None, ge=0, le=1)
    """Whether the clave B.01 prestaciones include the remaining non-exempt
    art. 17.2.a).1a prestaciones (position 394)."""
    perceptor_mediador_flag: str | None = Field(default=None, max_length=1)
    """Modelo 193 'X' flag (position 76) marking a perceptor that is itself a
    mediator entity paying by proxy, declared only for claves A, B and D."""
    clave_codigo: int | None = Field(default=None, ge=1, le=4)
    """Modelo 193 clave codigo (position 79) identifying what the codigo emisor
    and ISIN fields carry, always recorded for claves A, B and D (clave 4 is
    the general case)."""
    codigo_emisor: str | None = Field(default=None, max_length=12)
    """Modelo 193 codigo emisor (positions 80-91), declared only for claves A,
    B and D: the issuer's NIF for clave codigo 1/4, empty for 2, ZXX country
    code for 3."""
    naturaleza: str | None = Field(default=None, pattern=r"^\d{2}$")
    """Modelo 193 naturaleza (positions 93-94): the two-digit subclave of the
    clave de percepcion, always recorded."""
    pago: int | None = Field(default=None, ge=1, le=5)
    """Modelo 193 pago (position 95): who paid, always recorded for claves A,
    B and D (1 emisor, 2/3/4 mediador, 5 other mediation)."""
    tipo_codigo: str | None = Field(default=None, pattern=r"^[COP]$")
    """Modelo 193 tipo codigo (position 96): what the codigo cuenta field
    holds, always recorded for claves A, B and D."""
    codigo_cuenta: str | None = Field(default=None, max_length=20)
    """Modelo 193 codigo cuenta valores / numero operacion prestamo (positions
    97-116), recorded only when a financial entity manages the valores."""
    pendiente_flag: str | None = Field(default=None, max_length=1)
    """Modelo 193 'X' flag (position 117) marking percepciones devengadas but
    not yet paid because the holder did not claim them."""
    tipo_percepcion: int | None = Field(default=None, ge=1, le=2)
    """Modelo 193 tipo de percepcion (position 122): 1 dinerarias, 2 en
    especie, always recorded."""
    reducciones: Decimal = Decimal("0")
    """Modelo 193 art. 26.2 reductions (positions 139-151) applied when the
    perceptor is an IRPF contribuyente; the design's own zeros when none."""
    base_retenciones: Decimal = Decimal("0")
    """Modelo 193 base de retenciones e ingresos a cuenta (positions 152-164);
    the design's own zeros when no content."""
    porcentaje_retencion: Percentage = PERCENTAGE_MIN
    """Modelo 193 retention/ingreso-a-cuenta percentage applied (positions
    165-168), generally 19 with the design's clave-naturaleza specific rates;
    the last percentage applied when several were used."""
    penalizaciones: Decimal = Decimal("0")
    """Modelo 193 penalizaciones (positions 182-192), declared only for claves
    B and D; the design's own zeros when none."""
    isin_code: str | None = Field(default=None, max_length=12)
    """Modelo 193 codigo ISIN (positions 193-204, 2025 edition), recorded when
    clave codigo is 2 or 4."""
    naturaleza_declarante: str | None = Field(default=None, max_length=1)
    """Modelo 193 perceptor-record naturaleza del declarante (position 208):
    'S' when the declarante is outside the design's categories, blank
    otherwise -- recorded-when-applicable."""
    fecha_inicio_prestamo: str | None = Field(default=None, pattern=r"^\d{8}$")
    """Modelo 193 fecha de inicio del prestamo (positions 209-216, AAAAMMDD),
    declared only when tipo codigo is 'P'."""
    fecha_vencimiento_prestamo: str | None = Field(default=None, pattern=r"^\d{8}$")
    """Modelo 193 fecha de vencimiento del prestamo (positions 217-224,
    AAAAMMDD), declared only when tipo codigo is 'P'."""
    compensaciones: Decimal = Decimal("0")
    """Modelo 193 compensaciones (positions 225-236), declared only for
    prestamo de valores rows; the design's own zeros when none."""
    garantias: Decimal = Decimal("0")
    """Modelo 193 garantias (positions 237-248), declared only for prestamo de
    valores rows; the design's own zeros when none."""
    nif_pagador_anterior: TaxIdIdentityToken | None = Field(default=None, min_length=9, max_length=9)
    """Modelo 193 NIF of the immediately previous payer in the payment chain
    (positions 322-330), obligatory when pago is 2-5 except where the previous
    payer is foreign without a Spanish NIF -- recorded-when-applicable."""
    fecha_devengo: str | None = Field(default=None, pattern=r"^\d{8}$")
    """Modelo 193 fecha de devengo (positions 331-338, DDMMAAAA), declared only
    for clave A."""
    clave_mercado: str | None = Field(default=None, pattern=r"^[A-D]$")
    """Modelo 193 clave de mercado (position 339), always recorded for claves
    A, B and D."""
    numero_orden: int | None = Field(default=None, ge=1, le=9999999)
    """Modelo 193 numero de orden (positions 315-321): the sequential record
    number the design assigns each perceptor record. Derived by the resolver
    from the row order; a supplied value must not disagree."""

    _country_code_uppercase = field_validator("country_code")(optional_uppercase_alpha_code("country_code"))

    @field_validator("clave", mode="before")
    @classmethod
    def _coerce_clave(cls, value: object) -> object:
        """Hydrate the raw clave token to its :class:`RetencionClave` member.

        The strict model config does not coerce ``str`` -> ``StrEnum``; the parser /
        loader supplies the raw uppercase token (``"A"``), lifted here to
        ``RetencionClave.A``. An unknown token (outside A-L, lowercase, or
        multi-char) raises -- the closed-set hardening that replaces the former
        uppercase-only check.
        """
        if isinstance(value, str) and not isinstance(value, RetencionClave):
            return RetencionClave(value)
        return value

    @field_validator(
        "percibido_dinerario",
        "percibido_especie",
        "retencion_practicada",
        "ingreso_a_cuenta",
        "ingreso_a_cuenta_repercutido",
        "reducciones_aplicables",
        "gastos_deducibles",
        "pension_compensatoria",
        "anualidades_alimentos",
        "incapacity_cash_perception",
        "incapacity_cash_withholding",
        "incapacity_kind_value",
        "incapacity_kind_ingreso_a_cuenta",
        "incapacity_kind_repercutido",
        "foral_retention_estatal",
        "foral_retention_navarra",
        "foral_retention_araba",
        "foral_retention_gipuzkoa",
        "foral_retention_bizkaia",
        "reducciones",
        "base_retenciones",
        "penalizaciones",
        "compensaciones",
        "garantias",
    )
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise RegistryValidationError("withholding amounts must be non-negative")
        return value


class WithholdingObservationRequirement(BaseModel):
    """Withholding-source slice declared by one or more withholding bindings."""

    model_config = STRICT_FROZEN_CONFIG

    binding_ids: tuple[BindingId, ...] = Field(min_length=1)
    claves: tuple[RetencionClave, ...] = ()

    @field_validator("claves", mode="before")
    @classmethod
    def _coerce_claves(cls, value: object) -> object:
        """Hydrate each raw clave token to its :class:`RetencionClave` member (strict config)."""
        try:
            tokens = _CLAVE_TOKEN_SEQUENCE_ADAPTER.validate_python(value)
        except ValidationError:
            return value
        return tuple(
            RetencionClave(item) if isinstance(item, str) and not isinstance(item, RetencionClave) else item
            for item in tokens
        )

    _values_unique = field_validator("binding_ids", "claves")(unique_tuple("withholding requirement tuple"))


class _WithholdingSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    # Promoted from ``str`` to a typed Literal so the snapshot-build
    # shape gate rejects unknown fact values, mirroring the runtime
    # check the handler does against _WITHHOLDING_FACTS. Audit
    # selector-drift F2.
    fact: _WithholdingFact
    claves: tuple[str, ...] = ()
    row_field: _WithholdingRowField | None = None
    grouping: _WithholdingGrouping | None = None
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


def _withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    try:
        return _WithholdingSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed withholding selector") from exc


def validate_withholding_binding_selector_shape(binding: DataBindingDefinition) -> list[str]:
    """Validate withholding selector shape and fact/op invariants for snapshot build."""
    try:
        _WithholdingSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        return [
            f"binding {binding.id!r} (source={binding.source!r}) selector violates "
            f"{_WithholdingSelector.__name__}: {exc}",
        ]
    try:
        _validated_withholding_selector(binding)
    except RegistryValidationError as exc:
        return [f"binding {binding.id!r} (source={binding.source!r}) withholding invariants violated: {exc}"]
    return []


def _validated_withholding_selector(binding: DataBindingDefinition) -> _WithholdingSelector:
    selector = _withholding_selector(binding)
    if selector.fact not in _WITHHOLDING_FACTS:
        raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact {selector.fact!r}")
    op = binding_aggregation_op(binding)
    if selector.fact in {"perceptor_count", "percepcion_count"} and op != BindingAggregationOp.COUNT_DISTINCT:
        raise RegistryValidationError(
            f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'count_distinct'",
        )
    sum_facts = {"percibido_sum", "retencion_sum", "retenciones_ingresadas_sum"}
    if selector.fact in sum_facts and op != BindingAggregationOp.SUM:
        raise RegistryValidationError(f"binding {binding.id!r} fact {selector.fact!r} requires aggregation op 'sum'")
    if selector.fact == "row_field":
        if op != BindingAggregationOp.ROWS:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
        if selector.row_field is None:
            raise RegistryValidationError(
                f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key",
            )
        if selector.grouping is None:
            raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'grouping' selector key")
    return selector


def withholding_binding_requirements(
    revision: ModeloRevision,
) -> tuple[WithholdingObservationRequirement, ...]:
    """Return :class:`WithholdingObservationRequirement` slices needed by ``revision``'s withholding bindings.

    The :class:`ModeloRevision` is introspected for withholding bindings and
    grouped by the clave filters their selectors declare.
    """
    grouped: dict[tuple[RetencionClave, ...], set[BindingId]] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        key = tuple(sorted(RetencionClave(clave) for clave in selector.claves))
        grouped.setdefault(key, set()).add(binding.id)
    return tuple(
        WithholdingObservationRequirement(
            binding_ids=tuple(sorted(binding_ids)),
            claves=claves,
        )
        for claves, binding_ids in sorted(grouped.items())
    )


def _filter_withholding_observations(
    observations: Iterable[WithholdingObservation],
    selector: _WithholdingSelector,
) -> Iterable[WithholdingObservation]:
    clave_filter = set(selector.claves)
    for observation in observations:
        if clave_filter and observation.clave not in clave_filter:
            continue
        yield observation


def distinct_percepcion_keys(
    observations: Iterable[WithholdingObservation],
) -> set[tuple[str, RetencionClave, str]]:
    """Return the distinct ``(perceptor, clave, subclave)`` percepción keys.

    Modelo 190's "número total de percepciones" counts DISTINCT type-2
    "registro de perceptor" records (AEAT Diseño de Registros), not distinct
    NIFs: one perceptor paid under two claves files two percepciones. The key is
    therefore clave-bearing.

    Shared so the bound ``percepcion_count`` fact and the per-clave breakdown
    count the same thing. Grouping by clave and keying on ``(perceptor,
    subclave)`` yields the same per-clave counts as this key does across a
    scope, which is why the breakdown can build on it.
    """
    return {(obs.perceptor_tax_id, obs.clave, obs.subclave) for obs in observations}


def percibido_total(observations: Iterable[WithholdingObservation]) -> Decimal:
    """Sum percibido dinerario, en especie, and both incapacidad-laboral parts.

    The base amount facts carry the NON-incapacidad part (the design field's own
    meaning); the incapacidad blocks are separate parts the design files at
    255-321, so the row's full percibido total is the four magnitudes together.
    Shared by the bound ``percibido_sum`` fact and the per-clave breakdown so a
    change to what counts as percibido reaches both.
    """
    return sum(
        (
            obs.percibido_dinerario + obs.percibido_especie + obs.incapacity_cash_perception + obs.incapacity_kind_value
            for obs in observations
        ),
        Decimal("0"),
    )


def _retenciones_ingresadas_total(observations: Iterable[WithholdingObservation]) -> Decimal:
    """Sum the 169-181 retentions for the rows design position 175 folds in.

    The declarante's RETENCIONES E INGRESOS A CUENTA INGRESADOS field is the
    design's own declared sum: the retenciones e ingresos a cuenta of every
    perceptor row whose clave de percepcion is C, plus the A/B/D rows whose
    pago is 1 (emisor) or 3 (mediador de valor extranjero).
    """
    total = Decimal("0")
    for observation in observations:
        clave_code = str(observation.clave)
        if clave_code == "C" or (clave_code in {"A", "B", "D"} and observation.pago in (1, 3)):
            total += observation.retencion_practicada + observation.ingreso_a_cuenta
    return total


def retencion_total(observations: Iterable[WithholdingObservation]) -> Decimal:
    """Sum retención practicada, ingreso a cuenta, and the incap retentions.

    The base amount facts carry the NON-incapacidad part; the retentions on the
    incapacidad-laboral percepciones file in their own design block, so the
    row's full retenido total is the four magnitudes together. Shared by the
    bound ``retencion_sum`` fact and the per-clave breakdown so a change to what
    counts as retenido reaches both.
    """
    return sum(
        (
            obs.retencion_practicada
            + obs.ingreso_a_cuenta
            + obs.incapacity_cash_withholding
            + obs.incapacity_kind_ingreso_a_cuenta
            for obs in observations
        ),
        Decimal("0"),
    )


def resolve_withholding_binding_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[BindingId, Decimal]:
    """Resolve scalar withholding-source bindings into Decimal aggregates.

    The :class:`ModeloRevision` contributes scalar withholding bindings; row
    producer bindings are handled by ``resolve_withholding_binding_row_values``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact == "row_field":
            continue
        scope_filtered = tuple(_filter_withholding_observations(available, selector))
        if selector.fact == "perceptor_count":
            resolved[binding.id] = Decimal(len({obs.perceptor_tax_id for obs in scope_filtered}))
        elif selector.fact == "percepcion_count":
            resolved[binding.id] = Decimal(len(distinct_percepcion_keys(scope_filtered)))
        elif selector.fact == "percibido_sum":
            resolved[binding.id] = percibido_total(scope_filtered)
        elif selector.fact == "retencion_sum":
            resolved[binding.id] = retencion_total(scope_filtered)
        elif selector.fact == "retenciones_ingresadas_sum":
            resolved[binding.id] = _retenciones_ingresadas_total(scope_filtered)
        else:  # pragma: no cover - guarded by validator
            raise RegistryValidationError(f"binding {binding.id!r} declares unsupported withholding fact")
    return resolved


def resolve_withholding_binding_row_values(
    revision: ModeloRevision,
    observations: Iterable[WithholdingObservation],
) -> dict[tuple[BindingId, int], Decimal | str]:
    """Resolve row-producer withholding bindings into per-row indexed values.

    The :class:`ModeloRevision` contributes row-field withholding bindings,
    which are grouped into deterministic per-row output slots.
    """
    available = tuple(observations)
    resolved: dict[tuple[BindingId, int], Decimal | str] = {}
    cohorts: dict[
        tuple[_WithholdingGrouping, tuple[str, ...]],
        list[tuple[DataBindingDefinition, _WithholdingSelector]],
    ] = {}
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.WITHHOLDING:
            continue
        selector = _validated_withholding_selector(binding)
        if selector.fact != "row_field":
            continue
        assert selector.grouping is not None
        cohort_key = (selector.grouping, tuple(sorted(selector.claves)))
        cohorts.setdefault(cohort_key, []).append((binding, selector))
    for cohort_key, members in cohorts.items():
        grouping = cohort_key[0]
        _, sample_selector = members[0]
        scope_filtered = tuple(_filter_withholding_observations(available, sample_selector))
        required_fields = frozenset(selector.row_field for _, selector in members if selector.row_field is not None)
        from ._withholding_rows import _build_withholding_rows

        rows = _build_withholding_rows(grouping, scope_filtered, required_fields=required_fields)
        for binding, selector in members:
            assert selector.row_field is not None
            for row_index, row in enumerate(rows, start=1):
                value = row.get(selector.row_field)
                if value is None:
                    raise RegistryValidationError(
                        f"binding {binding.id!r} row_field {selector.row_field!r} not produced "
                        f"for grouping {grouping!r}",
                    )
                resolved[(binding.id, row_index)] = value
    return resolved


class WithholdingClaveBreakdown(BaseModel):
    """One per-clave row of the Modelo 190 retención reconciliation breakdown.

    Groups the per-perceptor-clave withholding detail (the AEAT Diseño de
    Registros type-2 records) by ``clave de percepción`` and carries that clave's
    distinct percepción count and percibido / retención magnitudes. The figures
    reuse the scalar withholding-fact arithmetic
    (:func:`resolve_withholding_binding_values`): ``percepcion_count`` is the
    distinct ``(perceptor, clave, subclave)`` count, ``percibido_total`` is
    ``percibido_dinerario + percibido_especie``, and ``retencion_total`` is
    ``retencion_practicada + ingreso_a_cuenta``. It is a projection of the same
    store the percepciones-count resolver reads, so the operator can reconcile
    the annual Modelo 190 totals against the individual Modelo 111 quarterly
    filings clave by clave.
    """

    model_config = STRICT_FROZEN_CONFIG

    clave: RetencionClave
    percepcion_count: NonNegativeInt
    percibido_total: Decimal = Field(ge=Decimal("0"))
    retencion_total: Decimal = Field(ge=Decimal("0"))


def aggregate_withholding_by_clave(
    observations: Iterable[WithholdingObservation],
) -> tuple[WithholdingClaveBreakdown, ...]:
    """Project withholding observations into :class:`WithholdingClaveBreakdown` rows.

    Pure function: identical observations in any order yield the same tuple,
    sorted by ``clave``. No new aggregation is introduced — each magnitude is
    produced by the same :func:`distinct_percepcion_keys` /
    :func:`percibido_total` / :func:`retencion_total` helper that
    :func:`resolve_withholding_binding_values` uses for the corresponding bound
    fact, so the breakdown cannot drift from the facts that feed the
    calculation. The clave is the grouping axis here and part of the key there;
    grouping first and counting the clave-bearing key within each group gives
    the same per-clave totals.

    That sentence used to be a claim rather than a guarantee: this function
    re-implemented all three formulas inline. An operator reconciles the annual
    Modelo 190 against the four quarterly Modelo 111 filings from this
    breakdown, so a formula changed in the resolver alone would have shown up
    as a reconciliation mismatch with nothing pointing at the cause.
    """
    by_clave: dict[RetencionClave, list[WithholdingObservation]] = {}
    for observation in observations:
        by_clave.setdefault(observation.clave, []).append(observation)
    return tuple(
        WithholdingClaveBreakdown(
            clave=clave,
            percepcion_count=len(distinct_percepcion_keys(group)),
            percibido_total=percibido_total(group),
            retencion_total=retencion_total(group),
        )
        for clave, group in sorted(by_clave.items())
    )


class WithholdingTotalsParity(BaseModel):
    """Totals-parity verdict between per-perceptor withholding rows and the Modelo 190 resumen-anual summary casillas.

    Modelo 190's summary casillas (``decl.percepciones-total``,
    ``decl.retenciones-total``) are computed by SUMMING the taxpayer's four
    Modelo 111 quarterly filings (``source = "relation_prefill"``,
    ``op = "sum"`` over casillas ``02/05/08/.../26`` and ``28`` respectively) —
    an entirely INDEPENDENT source from the per-perceptor-clave
    :class:`WithholdingObservation` detail (the AEAT Diseño de Registros type-2
    "registro de perceptor" rows, ``source = "withholding"``) that materialises
    the ``modelo-190-perceptor-row-*`` bindings and the distinct-percepción
    count. Nothing in the registry cross-checks that the two sources agree.

    This model is the pure comparison result of that cross-check: the sum of
    every persisted perceptor's ``percibido_dinerario + percibido_especie``
    against the resolved ``decl.percepciones-total`` value, and the sum of
    every persisted perceptor's ``retencion_practicada + ingreso_a_cuenta``
    against the resolved ``decl.retenciones-total`` value. ``is_consistent``
    is ``True`` only when both deltas are within ``tolerance`` — a divergence
    on either side surfaces as a loud, actionable finding
    (``no-silent-under-declaration``), never a silent pass.
    """

    model_config = STRICT_FROZEN_CONFIG

    percepciones_row_total: Decimal = Field(ge=Decimal("0"))
    percepciones_summary_total: Decimal = Field(ge=Decimal("0"))
    percepciones_delta: Decimal
    retenciones_row_total: Decimal = Field(ge=Decimal("0"))
    retenciones_summary_total: Decimal = Field(ge=Decimal("0"))
    retenciones_delta: Decimal
    row_count: NonNegativeInt
    tolerance: Decimal = Field(ge=Decimal("0"))
    is_consistent: bool


def compute_withholding_totals_parity(
    observations: Iterable[WithholdingObservation],
    *,
    percepciones_summary_total: Decimal,
    retenciones_summary_total: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> WithholdingTotalsParity:
    """Cross-check summed per-perceptor withholding rows against the resolved Modelo 190 summary casillas.

    Args:
        observations: The persisted per-perceptor-clave
            :class:`WithholdingObservation` rows (the AEAT Diseño de Registros
            type-2 "registro de perceptor" detail).
        percepciones_summary_total: The resolved value of casilla
            ``decl.percepciones-total`` (the M111-relation-derived summary
            total), typically read from
            ``revision.casilla_values["decl.percepciones-total"]``.
        retenciones_summary_total: The resolved value of casilla
            ``decl.retenciones-total``, typically read from
            ``revision.casilla_values["decl.retenciones-total"]``.
        tolerance: Maximum absolute delta (EUR) that does not surface a
            divergence. THE REGISTRY IS THE AUTHORITY FOR THIS VALUE and
            publishes it per revision: resolve it with
            ``snapshot.verification_policy().tolerance`` and pass it. The
            default is exact equality rather than a cent, because Modelo 190's
            own 2025 revision publishes exact equality (``0.00``) -- a
            hardcoded cent here would silently absorb a genuine one-cent
            under-declaration on exactly the modelo this function is named
            for.

    Returns:
        A :class:`WithholdingTotalsParity` verdict. ``is_consistent`` is
        ``False`` whenever either summed total diverges from its
        corresponding summary casilla by more than ``tolerance`` — a missing
        or dropped perceptor row under-declares the row-level total below the
        summary casilla and must surface as a divergence, never silently
        collapse into ``is_consistent=True``.
    """
    rows = tuple(observations)
    percepciones_row_total = percibido_total(rows)
    retenciones_row_total = retencion_total(rows)
    percepciones_delta = percepciones_row_total - percepciones_summary_total
    retenciones_delta = retenciones_row_total - retenciones_summary_total
    is_consistent = abs(percepciones_delta) <= tolerance and abs(retenciones_delta) <= tolerance
    return WithholdingTotalsParity(
        percepciones_row_total=percepciones_row_total,
        percepciones_summary_total=percepciones_summary_total,
        percepciones_delta=percepciones_delta,
        retenciones_row_total=retenciones_row_total,
        retenciones_summary_total=retenciones_summary_total,
        retenciones_delta=retenciones_delta,
        row_count=len(rows),
        tolerance=tolerance,
        is_consistent=is_consistent,
    )


WithholdingSelector = _WithholdingSelector
