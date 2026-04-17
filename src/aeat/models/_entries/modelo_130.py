"""Modelo 130 — pago fraccionado IRPF (estimación directa)."""

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
    code=ModeloCode.MODELO_130,
    official_name_es="Pago fraccionado IRPF. Estimación directa",
    display_label={
        "es": "Pago fraccionado IRPF. Estimación directa",
        "en": "IRPF fractional payment — direct estimation",
        "hu": "IRPF részletfizetés — közvetlen becslés",
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
            "99",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a99",
            "Establece la obligación general de practicar retenciones, ingresos a cuenta y "
            "pagos fraccionados como pagos a cuenta del IRPF.",
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
        ),
        optional=(),
        trigger_notes_es=(
            "Obligatorio para autónomos en estimación directa cuyo rendimiento no esté "
            "sujeto a retención en al menos el 70% (regla RD 439/2007 art 110.3.b). "
            "Mutuamente excluyente con el modelo 131."
        ),
    ),
    caps_into=ModeloCode.MODELO_100,
    related_modelos=(ModeloCode.MODELO_100, ModeloCode.MODELO_131),
    submission_portal=Portal.PORTAL_M130_PAGO_FRACCIONADO_ED,
    known_gotchas=("Negativo acumulado se arrastra dentro del año; resultado del período no puede ser negativo.",),
)
