"""Modelo 115 — retenciones arrendamientos urbanos."""

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
    code=ModeloCode.MODELO_115,
    official_name_es=(
        "Retenciones e ingresos a cuenta. Rentas o rendimientos procedentes del arrendamiento "
        "o subarrendamiento de inmuebles urbanos"
    ),
    display_label={
        "es": (
            "Retenciones e ingresos a cuenta. Rentas o rendimientos procedentes del "
            "arrendamiento o subarrendamiento de inmuebles urbanos"
        ),
        "en": "Withholdings on urban property rentals",
        "hu": "Városi ingatlanbérlet forrásadója",
    },
    category=ModeloCategory.RETENCIONES,
    cadence=ModeloCadence.QUARTERLY,
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
        trigger_notes_es=(
            "Obligatorio cuando el autónomo paga el alquiler del local de negocio a un "
            "arrendador sujeto a retención. Mapea a "
            "AutonomoProfile.pays_rent_with_retencion."
        ),
    ),
    caps_into=ModeloCode.MODELO_180,
    related_modelos=(ModeloCode.MODELO_180,),
    submission_portal=Portal.PORTAL_M115_RETENCIONES_ARRENDAMIENTOS,
    known_gotchas=(
        "Arrendamiento de vivienda LAU exento.",
        "RIRPF art 100 específico no disponible en corpus on-disk.",
    ),
)
