"""Closed taxonomies used by the modelo registry.

These enums are the keying dimensions the registry exposes on
:class:`aeat.models.ModeloMetadata`: the functional category a modelo
belongs to, the cadence at which it is filed, the taxpayer profile
space it applies to, and the legal-source provenance of its citations.
Every enum is a :class:`str.StrEnum` so members compare equal to their
canonical string representation across JSON boundaries.
"""

from __future__ import annotations

from enum import StrEnum


class ModeloCategory(StrEnum):
    """Functional category of an AEAT modelo.

    The closed set is the union of the categories the research D1
    inventory enumerates. Members map onto the "family" of taxes the
    modelo belongs to and drive CLI filtering only.
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

    ``AD_HOC`` covers event-driven forms (036, 037, 840). The
    deadline engine resolves exact windows at query time; cadence is
    the coarse grain the registry stores.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    AD_HOC = "ad_hoc"


class TaxpayerProfile(StrEnum):
    """The eight taxpayer profiles the modelo catalogue partitions by.

    The seven ``AUTONOMO_*`` members cover the autónomo profile space
    the research D2 matrix locks; ``SL`` is a first-class member for
    the sociedad limitada strand. IVA regime is tracked separately on
    :class:`aeat.deadlines.AutonomoProfile.iva_regime`.
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

    Distinguishes between primary statutory law (``LEY``,
    ``REAL_DECRETO``), secondary regulations (``REGLAMENTO``,
    ``ORDEN_MINISTERIAL``), curated Manual práctico excerpts, and raw
    BOE references. Used purely for display and filtering.
    """

    LEY = "ley"
    REAL_DECRETO = "real_decreto"
    ORDEN_MINISTERIAL = "orden_ministerial"
    REGLAMENTO = "reglamento"
    MANUAL_PRACTICO = "manual_practico"
    BOE = "boe"
