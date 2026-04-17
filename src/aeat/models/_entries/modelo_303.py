"""Modelo 303 — autoliquidación periódica del IVA."""

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
    code=ModeloCode.MODELO_303,
    official_name_es="Autoliquidación del IVA",
    display_label={
        "es": "Autoliquidación del IVA",
        "en": "Periodic VAT self-assessment",
        "hu": "Időszakos IVA-önbevallás",
    },
    category=ModeloCategory.IVA,
    cadence=ModeloCadence.QUARTERLY,
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
            "Regula la declaración-liquidación periódica del IVA, fija los plazos de "
            "presentación (trimestrales o mensuales según el régimen) y remite a los modelos "
            "oficiales aprobados por Orden Ministerial.",
        ),
    ),
    applicability=build_applicability(
        mandatory=tuple(TaxpayerProfile),
        optional=(),
        trigger_notes_es=(
            "Obligatorio para todo sujeto pasivo del IVA salvo régimen de recargo de "
            "equivalencia o exención. El gating fino por IVARegime "
            "(GENERAL/SIMPLIFICADO vs RECARGO_EQUIVALENCIA/EXENTO) se resuelve en el motor "
            "de plazos."
        ),
    ),
    caps_into=ModeloCode.MODELO_390,
    related_modelos=(ModeloCode.MODELO_390, ModeloCode.MODELO_349, ModeloCode.MODELO_369),
    submission_portal=Portal.PORTAL_M303_IVA_AUTOLIQUIDACION,
    known_gotchas=(
        "La pro-rata (art 104 LIVA) muta varias casillas.",
        "Los obligados a SII usan plazos mensuales distintos.",
    ),
)
