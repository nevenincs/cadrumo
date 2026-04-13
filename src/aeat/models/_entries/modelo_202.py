"""Modelo 202 — pago fraccionado del Impuesto sobre Sociedades."""

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
    code=ModeloCode.MODELO_202,
    official_name_es="Pago fraccionado del Impuesto sobre Sociedades",
    display_label={
        "es": "Pago fraccionado del Impuesto sobre Sociedades",
        "en": "Corporate income tax fractional payment",
        "hu": "Társasági adó részletfizetés",
    },
    category=ModeloCategory.SOCIEDADES,
    cadence=ModeloCadence.QUARTERLY,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales, incluida la presentación de "
            "declaraciones, autoliquidaciones y comunicaciones. Umbrella LGT del Modelo 202.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Solo aplica a sociedades; el régimen de cálculo se elige por INCN (umbral de "
            "6M EUR). El modelo se presenta en tres periodos (abril, octubre, diciembre); "
            "al no existir TRIMANUAL en ModeloCadence se cataloga como QUARTERLY."
        ),
    ),
    caps_into=ModeloCode.MODELO_200,
    related_modelos=(ModeloCode.MODELO_200,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 202",
    known_gotchas=(
        "Solo aplicable a SL.",
        "Tres periodos (abril/octubre/diciembre) en lugar de cuatro trimestres.",
    ),
)
