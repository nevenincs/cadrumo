"""Modelo 390 — declaración-resumen anual del IVA."""

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
    code=ModeloCode.MODELO_390,
    official_name_es="Declaración-resumen anual del IVA",
    display_label={
        "es": "Declaración-resumen anual del IVA",
        "en": "VAT annual summary return",
        "hu": "Éves IVA összesítő bevallás",
    },
    category=ModeloCategory.IVA,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "164",
            "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a164",
            "Enumera las obligaciones formales del sujeto pasivo del IVA: facturación, libros "
            "registro, declaraciones-liquidaciones periódicas y declaración-resumen anual.",
        ),
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "71",
            "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925#a71",
            "Regula la declaración-liquidación periódica del IVA y remite a los modelos "
            "oficiales aprobados por Orden Ministerial; el resumen anual deriva de las "
            "autoliquidaciones periódicas.",
        ),
    ),
    applicability=build_applicability(
        mandatory=tuple(TaxpayerProfile),
        optional=(),
        trigger_notes_es=(
            "Obligatorio para régimen general no acogido a SII; los filers en SII quedan "
            "exonerados. Gated por IVARegime en el motor de plazos."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_303,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 390",
    known_gotchas=(
        "Los filers en SII están exonerados del 390.",
        "Recargo de equivalencia usa 308/309 en lugar del 390.",
    ),
)
