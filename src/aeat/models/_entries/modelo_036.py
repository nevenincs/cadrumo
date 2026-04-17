"""Modelo 036 — declaración censal completa."""

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
    code=ModeloCode.MODELO_036,
    official_name_es=(
        "Declaración censal de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores"
    ),
    display_label={
        "es": (
            "Declaración censal de alta, modificación y baja en el Censo de Empresarios, Profesionales y Retenedores"
        ),
        "en": "Full census filing — registration, modification and deregistration",
        "hu": "Vállalkozói adónyilvántartási bevallás (teljes)",
    },
    category=ModeloCategory.CENSAL,
    cadence=ModeloCadence.AD_HOC,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones censales de los obligados tributarios: contenido, "
            "forma y plazos de las declaraciones de alta, modificación y baja.",
        ),
        make_citation(
            LegalCitationSource.LEY,
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales, incluidas las declaraciones censales.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(TaxpayerProfile.AUTONOMO_ED_UE, TaxpayerProfile.SL),
        optional=(
            TaxpayerProfile.AUTONOMO_ED_SOLO,
            TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS,
            TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES,
            TaxpayerProfile.AUTONOMO_ED_CON_ALQUILER,
            TaxpayerProfile.AUTONOMO_ED_BIENES_EXTRANJERO,
            TaxpayerProfile.AUTONOMO_EO,
        ),
        trigger_notes_es=(
            "Obligatorio en alta inicial, modificación de epígrafes IAE, domicilio, régimen "
            "de IVA o IRPF, alta en ROI, baja. Autónomos con ROI están forzados al 036; el "
            "resto puede usar 037."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_037,),
    submission_portal=Portal.PORTAL_M036_CENSAL,
    known_gotchas=(
        "Formulario completo; autónomo simple normalmente usa 037.",
        "Necesario para dar de alta ROI antes de presentar 349.",
    ),
)
