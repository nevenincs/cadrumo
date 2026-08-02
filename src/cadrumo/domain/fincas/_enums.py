"""Closed enumerations for the rental register.

Defines the closed catalogues the rental register's pydantic models
constrain themselves with: :class:`UseType` (finca purpose),
:class:`ExpenseCategory` (LIRPF art. 23.1 deductible-expense slots),
and :class:`ReduccionTier` (LIRPF art. 23.2 reducción outcomes).
"""

from __future__ import annotations

from enum import StrEnum


class UseType(StrEnum):
    """Closed catalogue of finca use types tracked by the rental register.

    Acts as the regime discriminator for the unified :class:`Finca`
    storage entity. Each member maps to one of three LIRPF treatments:

    * **Rendimiento del capital inmobiliario** (Ley 35/2006 IRPF
      Arts. 22-24): ``VIVIENDA_ARRENDADA``, ``LOCAL_COMERCIAL``,
      ``VIVIENDA_TURISTICA``.
    * **Imputación de rentas inmobiliarias** (Ley 35/2006 IRPF
      Art. 85): ``OTRO_INMUEBLE_NO_AFECTO``, ``VIVIENDA_DESOCUPADA``.
    * **No tax effect**: ``VIVIENDA_HABITUAL`` (excluded by Art. 85
      first paragraph).

    Members:
        VIVIENDA_ARRENDADA: Dwelling let to a tenant on a long-term /
            permanent-residence contract; feeds rental income,
            expense, amortization, and reduction aggregates via the
            per-contract register. ONLY this use type is eligible for
            the LIRPF Art. 23.2 reducción (the article applies to
            ``arrendamientos de bienes inmuebles destinados a
            vivienda``, which the second paragraph clarifies excludes
            touristic / temporary rentals).
        VIVIENDA_HABITUAL: Contribuyente's own habitual residence —
            no income line; excluded from imputación.
        OTRO_INMUEBLE_NO_AFECTO: Non-let, non-habitual urban
            inmueble; feeds real-estate imputation per LIRPF art. 85.
        LOCAL_COMERCIAL: Commercial premises; feeds the per-contract
            register on the same calculation surface as a vivienda
            arrendada, but is NOT eligible for the LIRPF art. 23.2
            reducción (the reducción applies only to arrendamientos
            de bienes inmuebles destinados a vivienda).
        VIVIENDA_DESOCUPADA: Empty dwelling not let — same imputación
            treatment as OTRO_INMUEBLE_NO_AFECTO; flagged distinctly
            for downstream IBI recargo modelling per Ley 12/2023
            disposición final tercera.
        VIVIENDA_TURISTICA: Dwelling let on a touristic / temporary
            basis (rental by season, by night, via short-stay
            platforms). Feeds the per-contract rendimiento aggregate
            on the same surface as VIVIENDA_ARRENDADA but is NOT
            eligible for the LIRPF Art. 23.2 reducción: the second
            paragraph of Art. 23.2 excludes arrendamientos "que se
            destinen a temporada o uso turístico". Distinct enum slot
            (rather than overloading LOCAL_COMERCIAL or letting the
            operator mark VIVIENDA_ARRENDADA) so the reducción-gate
            and casilla 0065 clave routing can refuse the reducción
            unambiguously. Authority: Ley 35/2006 IRPF Art. 23.2
            (second paragraph).
    """

    VIVIENDA_ARRENDADA = "VIVIENDA_ARRENDADA"
    VIVIENDA_HABITUAL = "VIVIENDA_HABITUAL"
    OTRO_INMUEBLE_NO_AFECTO = "OTRO_INMUEBLE_NO_AFECTO"
    LOCAL_COMERCIAL = "LOCAL_COMERCIAL"
    VIVIENDA_DESOCUPADA = "VIVIENDA_DESOCUPADA"
    VIVIENDA_TURISTICA = "VIVIENDA_TURISTICA"


class ExpenseCategory(StrEnum):
    """LIRPF art. 23.1 deductible-expense categories tracked per finca per year."""

    FINANCIACION_INTERESES = "FINANCIACION_INTERESES"
    CONSERVACION_REPARACION = "CONSERVACION_REPARACION"
    IBI_TRIBUTOS_NO_ESTATALES = "IBI_TRIBUTOS_NO_ESTATALES"
    COMUNIDAD = "COMUNIDAD"
    SEGUROS = "SEGUROS"
    SUMINISTROS = "SUMINISTROS"
    ADMINISTRACION_PORTERIA_VIGILANCIA = "ADMINISTRACION_PORTERIA_VIGILANCIA"
    FORMALIZACION_CONTRATO = "FORMALIZACION_CONTRATO"
    DEFENSA_JURIDICA = "DEFENSA_JURIDICA"
    SALDOS_DUDOSO_COBRO = "SALDOS_DUDOSO_COBRO"
    OTROS = "OTROS"


class ReduccionTier(StrEnum):
    """Closed catalogue of LIRPF art. 23.2 reducción outcomes.

    Distinct identifiers preserve audit traceability between the two
    60 % paths — DT 38ª (pre-26/05/2023 grandfathered contracts) vs
    art. 23.2.c (rehabilitation in the 2 years preceding the contract).
    Both yield 60 % numerically but cite different BOE provisions.

    The ``FORFEIT_LAU_17_6`` sentinel is emitted when a contract
    violates LAU art. 17.6 (rent cap for new contracts in declared
    zonas tensionadas where the landlord is a gran tenedor) — that
    forfeits the reducción entirely per Ley 12/2023 disposición
    final segunda apartado uno (closing paragraph).

    The ``NOT_APPLICABLE`` sentinel is emitted for a finca whose
    ``use_type`` is outside art. 23.2's scope entirely (commercial
    premises, touristic/temporary lettings) — a scope exclusion, distinct
    from ``FORFEIT_LAU_17_6``, which applies only to an otherwise-eligible
    ``VIVIENDA_ARRENDADA`` contract that fails the LAU rent-cap condition.
    """

    TIER_50 = "TIER_50"
    TIER_60_REHAB = "TIER_60_REHAB"
    TIER_60_GRANDFATHERED_DT38 = "TIER_60_GRANDFATHERED_DT38"
    TIER_70_JOVEN = "TIER_70_JOVEN"
    TIER_70_PUBLIC_ADMIN = "TIER_70_PUBLIC_ADMIN"
    TIER_90 = "TIER_90"
    FORFEIT_LAU_17_6 = "FORFEIT_LAU_17_6"
    NOT_APPLICABLE = "NOT_APPLICABLE"


__all__ = [
    "ExpenseCategory",
    "ReduccionTier",
    "UseType",
]
