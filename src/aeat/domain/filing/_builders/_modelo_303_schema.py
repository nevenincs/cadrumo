"""Hand-curated static casilla schema for Modelo 303.

Modelo 303 is the quarterly ``autoliquidación`` of IVA general regime filed
by Spanish autónomos and businesses. The current coverage scope is IVA
devengado on operaciones interiores régimen general (01-09), IVA deducible
(28-45), and resultado de la liquidación (64-71).

The numbering and formulas come from the *Manual práctico IVA 2025* (AEAT)
and the BOE-published Orden HAC/819/2024 modelo order. The full form
additionally carries régimen simplificado, intracomunitarias, importaciones,
recargo de equivalencia and regularización casillas which are out of scope
for this static schema.

Re-uses :class:`aeat.domain.filing._builders._modelo_130_schema.StaticCasillaSchema`
and :class:`aeat.domain.filing._builders._modelo_130_schema.StaticCasillaCollection`
because both classes are generic across modelos.
"""

from __future__ import annotations

from decimal import Decimal

from .._schema import SCHEMA_VERSION_DEFAULT
from ._modelo_130_schema import StaticCasillaCollection, StaticCasillaSchema


def _base(id_: str, description: str, *, defaulted: bool = True) -> StaticCasillaSchema:
    """Return a required, non-negative decimal base-imponible casilla.

    When ``defaulted`` is ``True`` (the default) the casilla
    silently defaults to zero when no input is supplied, matching
    the pragmatic behaviour that most deducible casillas have in
    practice. Pass ``defaulted=False`` for the three
    IVA-devengado bases (01/04/07) where a missing value must
    surface as a validation error.
    """
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=True,
        min_value=0,
        default=Decimal("0") if defaulted else None,
        description=description,
    )


def _rate(id_: str, rate: Decimal, description: str) -> StaticCasillaSchema:
    """Return a fixed-tipo casilla with the rate baked in as default."""
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        default=rate,
        description=description,
    )


def _formula(id_: str, inputs: tuple[str, ...], description: str) -> StaticCasillaSchema:
    """Return a computed casilla declaring its formula inputs."""
    return StaticCasillaSchema(
        id=id_,
        value_type="decimal",
        required=False,
        formula_inputs=inputs,
        description=description,
    )


MODELO_303_SCHEMA = StaticCasillaCollection(
    schema_version=SCHEMA_VERSION_DEFAULT,
    casillas=(
        # ── IVA devengado — régimen general operaciones interiores ──
        _base("01", "Base imponible gravada al 4%"),
        _rate("02", Decimal("4"), "Tipo reducido 4%"),
        _formula("03", ("01",), "Cuota devengada 4% = 01 x 0.04"),
        _base("04", "Base imponible gravada al 10%"),
        _rate("05", Decimal("10"), "Tipo reducido 10%"),
        _formula("06", ("04",), "Cuota devengada 10% = 04 x 0.10"),
        _base("07", "Base imponible gravada al 21%", defaulted=False),
        _rate("08", Decimal("21"), "Tipo general 21%"),
        _formula("09", ("07",), "Cuota devengada 21% = 07 x 0.21"),
        # ── IVA deducible — bases y cuotas ──
        _base("28", "Base imponible — operaciones interiores corrientes"),
        _base("29", "Cuota soportada deducible — operaciones interiores corrientes"),
        _base("30", "Base imponible — operaciones interiores bienes de inversión"),
        _base("31", "Cuota soportada deducible — bienes de inversión"),
        _base("32", "Base imponible — importaciones bienes corrientes"),
        _base("33", "Cuota soportada deducible — importaciones corrientes"),
        _base("34", "Base imponible — importaciones bienes de inversión"),
        _base("35", "Cuota soportada deducible — importaciones de inversión"),
        _base("36", "Base imponible — adquisiciones intracomunitarias corrientes"),
        _base("37", "Cuota soportada deducible — adquisiciones intracomunitarias corrientes"),
        _base("38", "Base imponible — adquisiciones intracomunitarias de inversión"),
        _base("39", "Cuota soportada deducible — adquisiciones intracomunitarias de inversión"),
        _base("40", "Rectificación de deducciones"),
        _base("41", "Compensaciones régimen especial A.G.P."),
        _base("42", "Regularización bienes de inversión"),
        _base("43", "Regularización por aplicación del porcentaje definitivo de prorrata"),
        _formula(
            "44",
            ("29", "31", "33", "35", "37", "39", "40", "41", "42", "43"),
            "Total a deducir = Σ cuotas deducibles + rectificaciones",
        ),
        _formula(
            "45",
            ("03", "06", "09", "44"),
            "Resultado régimen general = (03 + 06 + 09) - 44",
        ),
        # ── Resultado de la liquidación ──
        _formula("64", ("45",), "Suma de resultados = 45 (v1, sin régimen simplificado)"),
        StaticCasillaSchema(
            id="65",
            value_type="decimal",
            required=False,
            default=Decimal("100"),
            min_value=0,
            max_value=100,
            description="% atribuible a la Administración del Estado",
        ),
        _formula("66", ("64", "65"), "Atribuible al Estado = 64 x 65 / 100"),
        StaticCasillaSchema(
            id="67",
            value_type="decimal",
            required=False,
            default=Decimal("0"),
            min_value=0,
            description="Cuotas a compensar de períodos anteriores",
        ),
        _formula("69", ("66", "67"), "Resultado = 66 - 67"),
        _formula("71", ("69",), "Resultado de la autoliquidación"),
    ),
)
