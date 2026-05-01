"""Modelo 190 — resumen anual retenciones trabajo y actividades."""

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
    code=ModeloCode.MODELO_190,
    official_name_es=(
        "Resumen anual. Retenciones e ingresos a cuenta sobre rendimientos del trabajo y de actividades económicas"
    ),
    display_label={
        "es": (
            "Resumen anual. Retenciones e ingresos a cuenta sobre rendimientos del trabajo y de actividades económicas"
        ),
        "en": "Annual summary — employment and professional withholdings",
        "hu": "Éves összesítő — munka- és szabadfoglalkozású forrásadó",
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
            LegalCitationSource.LEY,
            "99",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a99",
            "Establece la obligación general de practicar retenciones, ingresos a cuenta y "
            "pagos fraccionados como pagos a cuenta del IRPF.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(
            TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS,
            TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES,
            TaxpayerProfile.SL,
        ),
        optional=(TaxpayerProfile.AUTONOMO_EO,),
        trigger_notes_es="Obligatorio cuando se ha presentado Modelo 111 durante el año.",
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_111,),
    submission_portal=Portal.PORTAL_M190_RESUMEN_TRABAJO,
    known_gotchas=("La taxonomía de subclaves es la máquina de estados del modelo.",),
)
