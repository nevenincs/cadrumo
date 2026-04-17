"""Modelo 193 — resumen anual de retenciones del modelo 123."""

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
    code=ModeloCode.MODELO_193,
    official_name_es=(
        "Resumen anual de retenciones e ingresos a cuenta sobre determinados rendimientos del capital mobiliario"
    ),
    display_label={
        "es": (
            "Resumen anual de retenciones e ingresos a cuenta sobre determinados rendimientos del capital mobiliario"
        ),
        "en": "Annual summary — certain movable-capital withholdings",
        "hu": "Éves összesítő — egyes tőkejövedelmek forrásadója",
    },
    category=ModeloCategory.INFORMATIVA,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "99",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a99",
            "Establece la obligación general de practicar retenciones, ingresos a cuenta y "
            "pagos fraccionados como pagos a cuenta del IRPF.",
        ),
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "108",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a108",
            "Desarrolla las obligaciones formales de los retenedores y obligados a ingresar "
            "a cuenta, incluyendo la presentación de resúmenes anuales.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.SL,),
        optional=(),
        trigger_notes_es="Obligatorio cuando durante el ejercicio se ha presentado modelo 123.",
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_123,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 193",
    known_gotchas=("Su lógica operativa es anual y depende de haber practicado retenciones del modelo 123.",),
)
