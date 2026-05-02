"""Closed taxonomies used by the modelo registry.

These enums are the keying dimensions the registry exposes on
:class:`aeat.domain.modelos.ModeloMetadata`: the functional category a
modelo belongs to, the cadence at which it is filed, the taxpayer
profile space it applies to, and the legal-source provenance of its
citations. Every enum is a :class:`enum.StrEnum` so members compare
equal to their canonical string representation across JSON boundaries.
"""

from __future__ import annotations

from enum import StrEnum


class ModeloCategory(StrEnum):
    """Functional category of an AEAT modelo.

    Members map onto the family of taxes the modelo belongs to and
    drive CLI filtering only.

    Attributes:
        IRPF: Personal income tax forms.
        IVA: Value-added tax forms.
        RETENCIONES: Withholding-tax forms.
        INFORMATIVA: Informational declarations.
        CENSAL: Census / registration forms (036, 037).
        SOCIEDADES: Corporate income tax forms.
        PATRIMONIO: Wealth-tax forms.
        OTROS: Forms outside the above families.
    """

    IRPF = "irpf"
    IVA = "iva"
    RETENCIONES = "retenciones"
    INFORMATIVA = "informativa"
    CENSAL = "censal"
    SOCIEDADES = "sociedades"
    PATRIMONIO = "patrimonio"
    OTROS = "otros"


class ModeloCadence(StrEnum):
    """Filing cadence of an AEAT modelo.

    The deadline engine resolves exact windows at query time; cadence
    is the coarse grain the registry stores.

    Attributes:
        MONTHLY: Filed every calendar month.
        QUARTERLY: Filed every calendar quarter.
        ANNUAL: Filed once per tax year.
        AD_HOC: Event-driven forms such as 036, 037, and 840.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"


class TaxpayerProfile(StrEnum):
    """The eight taxpayer profiles the modelo catalogue partitions by.

    The seven ``AUTONOMO_*`` members cover the autónomo profile space;
    ``SL`` is a first-class member for the sociedad limitada strand.
    The IVA regime is tracked separately on
    :class:`aeat.domain.deadlines.AutonomoProfile.iva_regime`.

    Attributes:
        AUTONOMO_ED_SOLO: Autónomo en estimación directa, no employees.
        AUTONOMO_ED_CON_EMPLEADOS: Autónomo en ED with employees.
        AUTONOMO_ED_CON_PROFESIONALES: Autónomo en ED paying
            professional retentions.
        AUTONOMO_ED_CON_ALQUILER: Autónomo en ED with rental income.
        AUTONOMO_ED_UE: Autónomo en ED operating across the EU.
        AUTONOMO_ED_BIENES_EXTRANJERO: Autónomo en ED holding foreign
            assets above the 720 reporting threshold.
        AUTONOMO_EO: Autónomo en estimación objetiva (módulos).
        SL: Sociedad limitada.
    """

    AUTONOMO_ED_SOLO = "autonomo_ed_solo"
    AUTONOMO_ED_CON_EMPLEADOS = "autonomo_ed_con_empleados"
    AUTONOMO_ED_CON_PROFESIONALES = "autonomo_ed_con_profesionales"
    AUTONOMO_ED_CON_ALQUILER = "autonomo_ed_con_alquiler"
    AUTONOMO_ED_UE = "autonomo_ed_ue"
    AUTONOMO_ED_BIENES_EXTRANJERO = "autonomo_ed_bienes_extranjero"
    AUTONOMO_EO = "autonomo_eo"
    SL = "sl"


class LegalCitationSource(StrEnum):
    """Source of a legal citation attached to a modelo.

    Distinguishes between primary statutory law, secondary
    regulations, curated *Manual práctico* excerpts, and raw BOE
    references. Used purely for display and filtering.

    Attributes:
        LEY: Statutory law (a *ley*).
        REAL_DECRETO: A *real decreto*.
        ORDEN_MINISTERIAL: A ministerial order.
        REGLAMENTO: A subordinate regulation (*reglamento*).
        MANUAL_PRACTICO: An excerpt from the AEAT *Manual práctico*.
        BOE: A raw BOE reference.
    """

    LEY = "ley"
    REAL_DECRETO = "real_decreto"
    ORDEN_MINISTERIAL = "orden_ministerial"
    REGLAMENTO = "reglamento"
    MANUAL_PRACTICO = "manual_practico"
    BOE = "boe"
