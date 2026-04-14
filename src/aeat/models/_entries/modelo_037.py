"""Modelo 037 — declaración censal simplificada."""

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

ENTRY: ModeloMetadata = build_entry(
    code=ModeloCode.MODELO_037,
    official_name_es="Declaración censal simplificada",
    display_label={
        "es": "Declaración censal simplificada",
        "en": "Simplified census filing",
        "hu": "Egyszerűsített adónyilvántartási bevallás",
    },
    category=ModeloCategory.CENSAL,
    cadence=ModeloCadence.AD_HOC,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones censales de los obligados tributarios: contenido, "
            "forma y plazos de las declaraciones de alta, modificación y baja.",
        ),
        make_citation(
            LegalCitationSource.LEY,
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales, incluidas las declaraciones censales.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_ED_SOLO, TaxpayerProfile.AUTONOMO_EO),
        optional=(
            TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS,
            TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES,
            TaxpayerProfile.AUTONOMO_ED_CON_ALQUILER,
            TaxpayerProfile.AUTONOMO_ED_BIENES_EXTRANJERO,
        ),
        trigger_notes_es=(
            "Opción simplificada para autónomos personas físicas que encajan en el "
            "subconjunto. Default para autonomo_ed_solo. El alta en ROI fuerza el paso a "
            "036."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_036,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 037 (Censo G322)",
    known_gotchas=("Camino de upgrade a 036 ante cambios de régimen.",),
)
