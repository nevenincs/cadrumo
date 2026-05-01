"""Modelo 369 — autoliquidación del IVA régimen OSS/IOSS."""

from __future__ import annotations

from ...portals import Portal
from .._categories import (
    LegalCitationSource,
    ModeloCadence,
    ModeloCategory,
    TaxpayerProfile,
)
from .._codes import ModeloCode
from .._metadata import ModeloMetadata
from ._common import (
    build_applicability,
    build_entry,
    make_citation,
)

ENTRY: ModeloMetadata = build_entry(
    code=ModeloCode.MODELO_369,
    official_name_es="Autoliquidación del IVA — régimen de ventanilla única (OSS/IOSS)",
    display_label={
        "es": "Autoliquidación del IVA — régimen de ventanilla única (OSS/IOSS)",
        "en": "OSS/IOSS VAT self-assessment",
        "hu": "OSS/IOSS IVA önbevallás",
    },
    category=ModeloCategory.IVA,
    cadence=ModeloCadence.QUARTERLY,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "164",
            "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a164",
            "Umbrella estatutario de las obligaciones formales del sujeto pasivo del IVA; el "
            "régimen OSS se desarrolla en el Título IX Capítulo XI de la Ley 37/1992, no "
            "disponible en el corpus on-disk.",
        ),
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "71",
            "https://www.boe.es/buscar/act.php?id=BOE-A-1992-28925#a71",
            "Regula la declaración-liquidación periódica del IVA; sirve de umbrella reglamentaria para el modelo 369.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(),
        optional=tuple(TaxpayerProfile),
        trigger_notes_es=(
            "Opt-in opcional para ventas B2C a distancia intracomunitarias y ciertos "
            "servicios digitales. Umbral anual de 10 000 EUR de ventas B2C UE."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_303,),
    submission_portal=Portal.PORTAL_M369_OSS_IOSS,
    known_gotchas=(
        "OSS requiere alta censal separada (Modelo 035).",
        "OSS Título IX Cap. XI no disponible en corpus on-disk.",
    ),
)
