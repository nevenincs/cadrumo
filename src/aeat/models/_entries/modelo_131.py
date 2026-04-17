"""Modelo 131 — pago fraccionado IRPF (estimación objetiva)."""

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
    code=ModeloCode.MODELO_131,
    official_name_es="Pago fraccionado IRPF. Estimación objetiva",
    display_label={
        "es": "Pago fraccionado IRPF. Estimación objetiva",
        "en": "IRPF fractional payment — objective estimation (modules)",
        "hu": "IRPF részletfizetés — objektív becslés (modulok)",
    },
    category=ModeloCategory.IRPF,
    cadence=ModeloCadence.QUARTERLY,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "110",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a110",
            "Fija el cálculo del pago fraccionado trimestral de los contribuyentes que "
            "desarrollan actividades económicas: estimación directa (20% del rendimiento neto) "
            "y estimación objetiva (tipos en función de magnitudes del módulo).",
        ),
        make_citation(
            LegalCitationSource.LEY,
            "31",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a31",
            "Regula el régimen de estimación objetiva (módulos), las magnitudes excluyentes y la renuncia al régimen.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_EO,),
        optional=(),
        trigger_notes_es=(
            "Obligatorio únicamente para autónomos en estimación objetiva (módulos). "
            "Mutuamente excluyente con el modelo 130."
        ),
    ),
    caps_into=ModeloCode.MODELO_100,
    related_modelos=(ModeloCode.MODELO_100, ModeloCode.MODELO_130),
    submission_portal=Portal.PORTAL_M131_PAGO_FRACCIONADO_EO,
    known_gotchas=("Aplica solo al perfil autonomo_eo.",),
)
