"""Modelo 100 — declaración anual del IRPF."""

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
    code=ModeloCode.MODELO_100,
    official_name_es="Declaración del Impuesto sobre la Renta de las Personas Físicas",
    display_label={
        "es": "Declaración del Impuesto sobre la Renta de las Personas Físicas",
        "en": "Annual personal income tax return",
        "hu": "Éves személyi jövedelemadó-bevallás (IRPF)",
    },
    category=ModeloCategory.IRPF,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "27",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a27",
            "Define qué se considera rendimiento de una actividad económica frente a los "
            "rendimientos del trabajo y del capital, y fija el criterio de ordenación por cuenta "
            "propia de los medios de producción y de los recursos humanos.",
        ),
        make_citation(
            LegalCitationSource.ORDEN_MINISTERIAL,
            "primero",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2025-5049#primero",
            "Aprueba los modelos de declaración del IRPF (Modelo 100) y del Impuesto sobre el "
            "Patrimonio (Modelo 714) correspondientes al ejercicio 2024, cuyo contenido figura "
            "en los anexos I y II de la propia orden.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(
            TaxpayerProfile.AUTONOMO_ED_SOLO,
            TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS,
            TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES,
            TaxpayerProfile.AUTONOMO_ED_CON_ALQUILER,
            TaxpayerProfile.AUTONOMO_ED_UE,
            TaxpayerProfile.AUTONOMO_ED_BIENES_EXTRANJERO,
            TaxpayerProfile.AUTONOMO_EO,
        ),
        optional=(),
        trigger_notes_es=(
            "Autónomos siempre obligados a presentar M100 independientemente de los umbrales "
            "generales del art. 96 Ley 35/2006; la regla de rendimientos de actividades "
            "económicas prevalece."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_130, ModeloCode.MODELO_131),
    submission_portal_hint="Sede Electrónica AEAT — Renta / Modelo 100",
    known_gotchas=(
        "Deducciones autonómicas varían por CCAA.",
        "El flujo del borrador tiene endpoint propio distinto del modelo raw.",
    ),
)
