"""Strict pydantic v2 substrate for the :mod:`aeat.domain.renta` subpackage.

Closed catalogues that classify Renta (IRPF) substrate axes — income
type, autonomous community of residence, estimación directa modality —
are :class:`enum.StrEnum` subclasses. The pattern mirrors the
:mod:`aeat.domain.vat` substrate (:class:`VATCategory`,
:class:`EUMemberState`, :class:`VATRateKind`) so the two domains share a
single closed-membership convention for substrate axes.

Per the calculation-truth-registry ADR, every Renta domain field that
classifies "what kind of X is this?" must use one of these closed enums
rather than a free-form ``str | None``. The Renta scope audit
(2026-05-07) lists this as Substrate-S1.
"""

from __future__ import annotations

from enum import StrEnum


class RentaIncomeType(StrEnum):
    """Closed catalogue of Renta IRPF income classification axes.

    Each member maps to a top-level branch of the LIRPF taxonomy:
    rendimientos del trabajo (art. 17), rendimientos del capital
    mobiliario (art. 25) split into the base-general fraction and the
    base-ahorro fraction, rendimientos del capital inmobiliario (art.
    22), actividades económicas in their three modalities (estimación
    directa normal art. 30, estimación directa simplificada art. 30
    + RIRPF art. 30, estimación objetiva art. 31), ganancias y pérdidas
    patrimoniales split into the base-general (transmisiones < 1 año
    pre-2014, etc.) and base-ahorro fractions, imputación de rentas
    (art. 85, transparencia fiscal internacional), and atribución de
    rentas (art. 88-90, entidades en régimen de atribución).
    """

    TRABAJO = "trabajo"
    CAPITAL_MOBILIARIO_GENERAL = "capital_mobiliario_general"
    CAPITAL_MOBILIARIO_AHORRO = "capital_mobiliario_ahorro"
    CAPITAL_INMOBILIARIO = "capital_inmobiliario"
    ACTIVIDADES_ECONOMICAS_DIRECTA_NORMAL = "actividades_economicas_directa_normal"
    ACTIVIDADES_ECONOMICAS_DIRECTA_SIMPLIFICADA = "actividades_economicas_directa_simplificada"
    ACTIVIDADES_ECONOMICAS_OBJETIVA = "actividades_economicas_objetiva"
    GANANCIAS_PERDIDAS_GENERAL = "ganancias_perdidas_general"
    GANANCIAS_PERDIDAS_AHORRO = "ganancias_perdidas_ahorro"
    IMPUTACION_RENTAS = "imputacion_rentas"
    ATRIBUCION_RENTAS = "atribucion_rentas"


class RentaCCAA(StrEnum):
    """Closed catalogue of the Spanish autonomous communities + Ciudades autónomas.

    Mirrors :class:`aeat.domain.vat.EUMemberState` shape (lowercase ISO
    code values). Covers the 17 autonomous communities (comunidades
    autónomas) plus the 2 autonomous cities (ciudades autónomas) of
    Ceuta and Melilla. Used by the Renta autonomic-deductions chain
    (Anexo B) and the autonomic escala (LIRPF art. 74).

    Foral regimes (País Vasco diputaciones forales, Comunidad Foral de
    Navarra) are represented as single members at the autonomous-
    community granularity. Operations that depend on the specific
    diputación foral (Álava / Bizkaia / Gipuzkoa) must use a separate
    enum or per-diputación selector layered on top.
    """

    AND = "and"  # Andalucía
    ARA = "ara"  # Aragón
    AST = "ast"  # Principado de Asturias
    BAL = "bal"  # Illes Balears
    CAN = "can"  # Canarias
    CAB = "cab"  # Cantabria
    CLM = "clm"  # Castilla-La Mancha
    CYL = "cyl"  # Castilla y León
    CAT = "cat"  # Cataluña / Catalunya
    EXT = "ext"  # Extremadura
    GAL = "gal"  # Galicia
    MAD = "mad"  # Comunidad de Madrid
    MUR = "mur"  # Región de Murcia
    NAV = "nav"  # Comunidad Foral de Navarra
    PVA = "pva"  # País Vasco / Euskadi
    LAR = "lar"  # La Rioja
    VAL = "val"  # Comunitat Valenciana
    CEU = "ceu"  # Ciudad Autónoma de Ceuta
    MEL = "mel"  # Ciudad Autónoma de Melilla


class EstimacionDirectaModalidad(StrEnum):
    """Closed catalogue for the estimación directa modality selector.

    Replaces the binding selector that maps casilla 0168 string values
    "N" / "S" to the normal / simplified modes. The bound value lives in
    the registry as `renta-{year}-modelo-100-estimacion-directa-es-normal`
    with selector ``true_value="N"`` and ``false_value="S"``; consumers
    resolve through this enum rather than parsing the raw string.

    LIRPF art. 30 distinguishes the two modalities by reference to
    Reglamento IRPF art. 28 thresholds (8 million EUR cifra de negocios
    in the prior year). The registry's per-year difficult-justification
    parameter (5 percent rate, 2,000 EUR cap) only applies in
    SIMPLIFICADA mode.
    """

    NORMAL = "normal"
    SIMPLIFICADA = "simplificada"


__all__ = [
    "EstimacionDirectaModalidad",
    "RentaCCAA",
    "RentaIncomeType",
]
