"""Encode the LIS art. 12.1.a) tabla de amortización lineal.

Provides the official Spanish corporate-income-tax amortization table
applicable to actividades económicas IRPF en estimación directa normal
per LIRPF art. 28. Each row of :data:`LIS_ART_12_LINEAL_TABLE` carries
an asset category, the maximum lineal coefficient and the maximum
amortization period — see :class:`AmortizationCategory` for field
definitions and :class:`AssetClass` for the closed enumeration of
categories.

The estimación directa simplificada régimen uses a separate
amortization table (Orden de 27 de marzo de 1998 in its vigent
version), NOT this table. Libertad de amortización (LIS arts. 12.3 and
102) bypasses the table for I+D, vehículos eléctricos (DA 18ª LIS via
Ley 31/2022, DA 59ª LIRPF via RD-Ley 4/2024), and PYMES new-asset
acquisition.

Source: Ley 27/2014 (LIS) art. 12.1.a) consolidated text, BOE id
``BOE-A-2014-12328``. The Reglamento del IS (RD 634/2015,
``BOE-A-2015-7771``) does NOT duplicate the table — the statutory text
in the Ley is the only authoritative source.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AssetClass(StrEnum):
    """Closed enumeration of LIS art. 12.1.a) asset categories.

    The table publishes ~30 distinct categories. Each member's value is
    a stable identifier in ``snake_case.dot`` form (for example
    ``"obra_civil.general"``) suitable for casilla naming and
    parameter-table keys.
    """

    OBRA_CIVIL_GENERAL = "obra_civil.general"
    OBRA_CIVIL_PAVIMENTOS = "obra_civil.pavimentos"
    OBRA_CIVIL_INFRA_MINERAS = "obra_civil.infraestructuras_obras_mineras"
    CENTRALES_HIDRAULICAS = "centrales.hidraulicas"
    CENTRALES_NUCLEARES = "centrales.nucleares"
    CENTRALES_CARBON = "centrales.carbon"
    CENTRALES_RENOVABLES = "centrales.renovables"
    CENTRALES_OTRAS = "centrales.otras"
    EDIFICIOS_INDUSTRIALES = "edificios.industriales"
    EDIFICIOS_ESCOMBRERAS = "edificios.escombreras"
    EDIFICIOS_ALMACENES = "edificios.almacenes_depositos"
    EDIFICIOS_COMERCIALES = "edificios.comerciales_administrativos_servicios_viviendas"
    INSTALACIONES_SUBESTACIONES = "instalaciones.subestaciones_redes"
    INSTALACIONES_CABLES = "instalaciones.cables"
    INSTALACIONES_RESTO = "instalaciones.resto"
    MAQUINARIA_GENERAL = "maquinaria.general"
    MAQUINARIA_MEDICOS = "maquinaria.equipos_medicos"
    TRANSPORTE_LOCOMOTORAS = "transporte.locomotoras_vagones_traccion"
    TRANSPORTE_BUQUES_AERONAVES = "transporte.buques_aeronaves"
    TRANSPORTE_INTERNO = "transporte.interno"
    TRANSPORTE_EXTERNO = "transporte.externo"
    TRANSPORTE_AUTOCAMIONES = "transporte.autocamiones"
    MOBILIARIO_GENERAL = "mobiliario.general"
    MOBILIARIO_LENCERIA = "mobiliario.lenceria"
    MOBILIARIO_CRISTALERIA = "mobiliario.cristaleria"
    MOBILIARIO_UTILES = "mobiliario.utiles_herramientas"
    MOBILIARIO_MOLDES = "mobiliario.moldes_matrices_modelos"
    MOBILIARIO_OTROS = "mobiliario.otros_enseres"
    ELECTRONICA_GENERAL = "electronica.equipos_electronicos"
    ELECTRONICA_INFORMATICA = "electronica.equipos_tratamiento_informacion"
    ELECTRONICA_SOFTWARE = "electronica.sistemas_programas_informaticos"
    PRODUCCIONES_AUDIOVISUALES = "producciones.audiovisuales"
    OTROS_ELEMENTOS = "otros.elementos"


class AmortizationCategory(BaseModel):
    """A single row of the LIS art. 12.1.a) lineal table.

    The two numeric fields establish the maximum lineal coefficient and
    the maximum amortization period. Either bound — whichever is more
    restrictive in practice — is the legal cap.

    Attributes:
        asset_class: Identifier of the asset category.
        coef_max_pct: Maximum lineal coefficient as a decimal percentage
            (for example ``Decimal("12.00")`` represents 12 %).
        period_max_years: Maximum amortization period in years.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    asset_class: AssetClass
    coef_max_pct: Decimal
    period_max_years: int


# Verbatim transcription of LIS art. 12.1.a) consolidated text.
# Source: Ley 27/2014, BOE-A-2014-12328, as published 2014-11-28 with
# subsequent reforms (none have touched art. 12.1.a) numerically as
# of 2026-02-28). The 2024-2025-2026 fiscal years all use this table.
LIS_ART_12_LINEAL_TABLE: tuple[AmortizationCategory, ...] = (
    AmortizationCategory(
        asset_class=AssetClass.OBRA_CIVIL_GENERAL,
        coef_max_pct=Decimal("2.00"),
        period_max_years=100,
    ),
    AmortizationCategory(
        asset_class=AssetClass.OBRA_CIVIL_PAVIMENTOS,
        coef_max_pct=Decimal("6.00"),
        period_max_years=34,
    ),
    AmortizationCategory(
        asset_class=AssetClass.OBRA_CIVIL_INFRA_MINERAS,
        coef_max_pct=Decimal("7.00"),
        period_max_years=30,
    ),
    AmortizationCategory(
        asset_class=AssetClass.CENTRALES_HIDRAULICAS,
        coef_max_pct=Decimal("2.00"),
        period_max_years=100,
    ),
    AmortizationCategory(
        asset_class=AssetClass.CENTRALES_NUCLEARES,
        coef_max_pct=Decimal("3.00"),
        period_max_years=60,
    ),
    AmortizationCategory(
        asset_class=AssetClass.CENTRALES_CARBON,
        coef_max_pct=Decimal("4.00"),
        period_max_years=50,
    ),
    AmortizationCategory(
        asset_class=AssetClass.CENTRALES_RENOVABLES,
        coef_max_pct=Decimal("7.00"),
        period_max_years=30,
    ),
    AmortizationCategory(
        asset_class=AssetClass.CENTRALES_OTRAS,
        coef_max_pct=Decimal("5.00"),
        period_max_years=40,
    ),
    AmortizationCategory(
        asset_class=AssetClass.EDIFICIOS_INDUSTRIALES,
        coef_max_pct=Decimal("3.00"),
        period_max_years=68,
    ),
    AmortizationCategory(
        asset_class=AssetClass.EDIFICIOS_ESCOMBRERAS,
        coef_max_pct=Decimal("4.00"),
        period_max_years=50,
    ),
    AmortizationCategory(
        asset_class=AssetClass.EDIFICIOS_ALMACENES,
        coef_max_pct=Decimal("7.00"),
        period_max_years=30,
    ),
    AmortizationCategory(
        asset_class=AssetClass.EDIFICIOS_COMERCIALES,
        coef_max_pct=Decimal("2.00"),
        period_max_years=100,
    ),
    AmortizationCategory(
        asset_class=AssetClass.INSTALACIONES_SUBESTACIONES,
        coef_max_pct=Decimal("5.00"),
        period_max_years=40,
    ),
    AmortizationCategory(
        asset_class=AssetClass.INSTALACIONES_CABLES,
        coef_max_pct=Decimal("7.00"),
        period_max_years=30,
    ),
    AmortizationCategory(
        asset_class=AssetClass.INSTALACIONES_RESTO,
        coef_max_pct=Decimal("10.00"),
        period_max_years=20,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MAQUINARIA_GENERAL,
        coef_max_pct=Decimal("12.00"),
        period_max_years=18,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MAQUINARIA_MEDICOS,
        coef_max_pct=Decimal("15.00"),
        period_max_years=14,
    ),
    AmortizationCategory(
        asset_class=AssetClass.TRANSPORTE_LOCOMOTORAS,
        coef_max_pct=Decimal("8.00"),
        period_max_years=25,
    ),
    AmortizationCategory(
        asset_class=AssetClass.TRANSPORTE_BUQUES_AERONAVES,
        coef_max_pct=Decimal("10.00"),
        period_max_years=20,
    ),
    AmortizationCategory(
        asset_class=AssetClass.TRANSPORTE_INTERNO,
        coef_max_pct=Decimal("10.00"),
        period_max_years=20,
    ),
    AmortizationCategory(
        asset_class=AssetClass.TRANSPORTE_EXTERNO,
        coef_max_pct=Decimal("16.00"),
        period_max_years=14,
    ),
    AmortizationCategory(
        asset_class=AssetClass.TRANSPORTE_AUTOCAMIONES,
        coef_max_pct=Decimal("20.00"),
        period_max_years=10,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_GENERAL,
        coef_max_pct=Decimal("10.00"),
        period_max_years=20,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_LENCERIA,
        coef_max_pct=Decimal("25.00"),
        period_max_years=8,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_CRISTALERIA,
        coef_max_pct=Decimal("50.00"),
        period_max_years=4,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_UTILES,
        coef_max_pct=Decimal("25.00"),
        period_max_years=8,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_MOLDES,
        coef_max_pct=Decimal("33.00"),
        period_max_years=6,
    ),
    AmortizationCategory(
        asset_class=AssetClass.MOBILIARIO_OTROS,
        coef_max_pct=Decimal("15.00"),
        period_max_years=14,
    ),
    AmortizationCategory(
        asset_class=AssetClass.ELECTRONICA_GENERAL,
        coef_max_pct=Decimal("20.00"),
        period_max_years=10,
    ),
    AmortizationCategory(
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        coef_max_pct=Decimal("25.00"),
        period_max_years=8,
    ),
    AmortizationCategory(
        asset_class=AssetClass.ELECTRONICA_SOFTWARE,
        coef_max_pct=Decimal("33.00"),
        period_max_years=6,
    ),
    AmortizationCategory(
        asset_class=AssetClass.PRODUCCIONES_AUDIOVISUALES,
        coef_max_pct=Decimal("33.00"),
        period_max_years=6,
    ),
    AmortizationCategory(
        asset_class=AssetClass.OTROS_ELEMENTOS,
        coef_max_pct=Decimal("10.00"),
        period_max_years=20,
    ),
)


__all__ = [
    "LIS_ART_12_LINEAL_TABLE",
    "AmortizationCategory",
    "AssetClass",
]
