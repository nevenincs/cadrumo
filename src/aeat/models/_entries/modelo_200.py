"""Modelo 200 — Impuesto sobre Sociedades anual."""

from __future__ import annotations

from aeat.models._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from aeat.models._codes import ModeloCode
from aeat.models._entries._common import (
    build_applicability,
    build_entry,
    make_citation,
)
from aeat.models._metadata import ModeloMetadata
from aeat.portals._codes import Portal

ENTRY: ModeloMetadata = build_entry(
    code=ModeloCode.MODELO_200,
    official_name_es="Declaración del Impuesto sobre Sociedades",
    display_label={
        "es": "Declaración del Impuesto sobre Sociedades",
        "en": "Corporate income tax return",
        "hu": "Társasági adóbevallás",
    },
    category=ModeloCategory.SOCIEDADES,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales, incluida la presentación de "
            "declaraciones, autoliquidaciones y comunicaciones. Sirve de umbrella LGT del "
            "Modelo 200.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.SL,),
        optional=(),
        trigger_notes_es="Aplica únicamente a sociedades (SL) con periodo impositivo anual.",
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_202, ModeloCode.MODELO_232),
    submission_portal=Portal.PORTAL_M200_SOCIEDADES_ANUAL,
    known_gotchas=(
        "Solo aplicable a SL.",
        "Ley 27/2014 del Impuesto sobre Sociedades no disponible en corpus on-disk.",
    ),
)
