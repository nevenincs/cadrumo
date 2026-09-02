"""Closed enumerations for the rental register.

Defines the closed catalogues the rental register's pydantic models
constrain themselves with: :class:`UseType` (finca purpose),
:class:`ExpenseCategory` (LIRPF art. 23.1 deductible-expense slots),
:class:`ReduccionTier` (LIRPF art. 23.2 reducción outcomes),
:class:`TitularidadRegime` (which right over the finca the contribuyente
holds) and :class:`TitularContribuyente` (casilla [0062] titular).
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


class TitularidadRegime(StrEnum):
    """Closed catalogue of the rights a contribuyente may hold over a finca.

    The regime selects which of the two declared percentages attributes
    the finca's figures to this contribuyente, and it is not derivable
    from the percentages themselves: a pleno propietario and a nudo
    propietario both declare a porcentaje de propiedad in casilla
    [0063] and no porcentaje de usufructo in casilla [0064], yet the
    first declares the property's income and the second declares
    nothing.

    Authority: *Manual práctico de Renta 2025*, Parte 1, Capítulo 4,
    "Individualización de los rendimientos del capital inmobiliario"
    (págs. 292-293, Art. 11.3 Ley IRPF) and Capítulo 10,
    "Individualización de las rentas inmobiliarias" (pág. 805).

    Members:
        NO_DECLARADA: The titularidad facts were never declared. A
            distinct state from any share, including a full one: the
            aggregation refuses rather than assuming sole full title.
        PLENO_DOMINIO: Full ownership of the declared porcentaje de
            propiedad. Attribution follows casilla [0063].
        NUDA_PROPIEDAD: Bare ownership, the usufructo resting with
            another party. Attribution is zero for both the rendimiento
            and the art. 85 imputación, whatever casilla [0063] says.
        USUFRUCTO: The contribuyente holds the derecho de usufructo.
            Attribution follows casilla [0064], and covers both the
            rendimiento and the imputación.
        PLENO_DOMINIO_Y_USUFRUCTO: Pleno dominio over part of the finca
            and usufructo over the rest. Legally real and declarable,
            but its amortización splits into two rules (Capítulo 4,
            "Gastos deducibles", pág. 281) of which the register models
            only one, so the aggregation refuses instead of guessing.
    """

    NO_DECLARADA = "NO_DECLARADA"
    PLENO_DOMINIO = "PLENO_DOMINIO"
    NUDA_PROPIEDAD = "NUDA_PROPIEDAD"
    USUFRUCTO = "USUFRUCTO"
    PLENO_DOMINIO_Y_USUFRUCTO = "PLENO_DOMINIO_Y_USUFRUCTO"


class TitularContribuyente(StrEnum):
    """Closed catalogue for casilla [0062], the titular of the inmueble.

    The declaration identifies the holder by their place in the unidad
    familiar, not by name or NIF: "Común" when a joint declaration's
    inmueble belongs to both cónyuges in equal parts, otherwise the
    member who holds total or partial title. Authority: *Manual
    práctico de Renta 2025*, Parte 1, Capítulo 4, "Declaración bienes
    inmuebles — Datos particulares de cada inmueble" (pág. 295).

    Members:
        COMUN: "Común" — a joint declaration where the inmueble belongs
            to both cónyuges in equal parts.
        PRIMER_DECLARANTE: "Primer declarante".
        CONYUGE: "Cónyuge".
        HIJO: "Hijo 1º", "Hijo 2º" …; the ordinal is carried beside
            this member rather than folded into it.
    """

    COMUN = "COMUN"
    PRIMER_DECLARANTE = "PRIMER_DECLARANTE"
    CONYUGE = "CONYUGE"
    HIJO = "HIJO"


__all__ = [
    "ExpenseCategory",
    "ReduccionTier",
    "TitularContribuyente",
    "TitularidadRegime",
    "UseType",
]
