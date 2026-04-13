"""Modelo 720 — declaración informativa sobre bienes y derechos en el extranjero."""

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
    code=ModeloCode.MODELO_720,
    official_name_es="Declaración informativa sobre bienes y derechos situados en el extranjero",
    display_label={
        "es": "Declaración informativa sobre bienes y derechos situados en el extranjero",
        "en": "Information return on assets and rights held abroad",
        "hu": "Adatszolgáltatás külföldön lévő vagyonról",
    },
    category=ModeloCategory.INFORMATIVA,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones de presentación de declaraciones informativas por "
            "parte de los obligados tributarios; umbrella reglamentaria del Modelo 720.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_ED_BIENES_EXTRANJERO,),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Obligatorio cuando se ostentan bienes en el extranjero por encima de 50 000 EUR "
            "en alguna de las tres categorías (cuentas, valores, inmuebles). Mapea a "
            "AutonomoProfile.bienes_extranjero_above_threshold."
        ),
    ),
    caps_into=None,
    related_modelos=(),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 720",
    known_gotchas=(
        "Sanciones específicas derogadas por STJUE C-788/19; la obligación informativa se mantiene.",
        "RGAT arts 42 bis/ter/54 bis no disponibles en corpus on-disk.",
    ),
)
