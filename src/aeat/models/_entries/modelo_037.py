"""Modelo 037 — declaración censal simplificada."""

from __future__ import annotations

from aeat.models._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
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
        mandatory=(),
        optional=(),
        trigger_notes_es=(
            "Modelo histórico suprimido por la Orden HAC/1526/2024 con efectos desde "
            "2025-02-03. Se conserva en el inventario para filing history anterior a esa "
            "fecha; las altas, modificaciones y bajas censales corrientes se canalizan por "
            "el modelo 036."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_036,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 037 (histórico hasta 2025-02-02)",
    known_gotchas=(
        "Suprimido desde 2025-02-03; no debe aparecer como camino censal corriente.",
        "El filing history previo a la supresión sigue pudiendo contener 037.",
    ),
)
