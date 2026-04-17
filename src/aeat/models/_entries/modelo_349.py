"""Modelo 349 — declaración recapitulativa de operaciones intracomunitarias."""

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
from aeat.portals import Portal

ENTRY: ModeloMetadata = build_entry(
    code=ModeloCode.MODELO_349,
    official_name_es="Declaración recapitulativa de operaciones intracomunitarias",
    display_label={
        "es": "Declaración recapitulativa de operaciones intracomunitarias",
        "en": "Recapitulative statement of intra-EU operations",
        "hu": "EU-n belüli ügyletek összesítő nyilatkozata",
    },
    category=ModeloCategory.INFORMATIVA,
    cadence=ModeloCadence.QUARTERLY,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones de presentación de declaraciones informativas por "
            "parte de los obligados tributarios, fijando el contenido mínimo, la forma y los "
            "plazos de presentación reglamentarios que sirven de base a los modelos anuales "
            "(347, 349, etc).",
        ),
        make_citation(
            LegalCitationSource.LEY,
            "164",
            "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a164",
            "Enumera las obligaciones formales del sujeto pasivo del IVA: facturación, libros "
            "registro, declaraciones-liquidaciones periódicas y declaración-resumen anual.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_ED_UE,),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Obligatorio cuando el autónomo realiza entregas o adquisiciones "
            "intracomunitarias. Cadencia trimestral por defecto; pasa a mensual si se supera "
            "el umbral rolling cuatrimestral de 50 000 EUR (art 81.3 RIVA — no disponible en "
            "corpus on-disk). Mapea a AutonomoProfile.does_intracomunitario."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_303,),
    submission_portal=Portal.PORTAL_M349_INTRACOMUNITARIAS,
    known_gotchas=(
        "Requiere alta en ROI (censo) vía Modelo 036.",
        "RIVA art 81.3 no disponible en corpus on-disk.",
    ),
)
