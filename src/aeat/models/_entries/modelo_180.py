"""Modelo 180 — resumen anual retenciones arrendamientos."""

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
    code=ModeloCode.MODELO_180,
    official_name_es=(
        "Resumen anual. Retenciones e ingresos a cuenta sobre rendimientos del arrendamiento de inmuebles urbanos"
    ),
    display_label={
        "es": (
            "Resumen anual. Retenciones e ingresos a cuenta sobre rendimientos del arrendamiento de inmuebles urbanos"
        ),
        "en": "Annual summary — urban rental withholdings",
        "hu": "Éves összesítő — városi ingatlanbérlet forrásadója",
    },
    category=ModeloCategory.INFORMATIVA,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones de presentación de declaraciones informativas por "
            "parte de los obligados tributarios, fijando el contenido mínimo, la forma y los "
            "plazos de presentación reglamentarios.",
        ),
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "109",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a109",
            "Desarrolla las obligaciones formales de los retenedores y obligados a ingresar "
            "a cuenta, incluyendo el modelo, el plazo de presentación y la comunicación de "
            "datos a la Administración tributaria.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_ED_CON_ALQUILER, TaxpayerProfile.SL),
        optional=(),
        trigger_notes_es="Obligatorio cuando se ha presentado Modelo 115 durante el año.",
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_115,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 180",
    known_gotchas=("Debe reconciliar con la suma de los cuatro 115 del ejercicio.",),
)
