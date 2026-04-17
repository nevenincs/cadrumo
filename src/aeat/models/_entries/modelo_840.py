"""Modelo 840 — Impuesto sobre Actividades Económicas (IAE)."""

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
from aeat.portals import Portal

ENTRY: ModeloMetadata = build_entry(
    code=ModeloCode.MODELO_840,
    official_name_es="Declaración del Impuesto sobre Actividades Económicas",
    display_label={
        "es": "Declaración del Impuesto sobre Actividades Económicas",
        "en": "Economic Activities Tax census declaration",
        "hu": "Gazdasági tevékenységek adója (IAE) nyilvántartási bevallás",
    },
    category=ModeloCategory.OTROS,
    cadence=ModeloCadence.AD_HOC,
    legal_basis=(
        make_citation(
            LegalCitationSource.LEY,
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales; sirve de umbrella LGT del IAE, "
            "cuya regulación sustantiva (TRLHL arts 78-91) no está disponible en el corpus "
            "on-disk.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Personas físicas y jurídicas con INCN < 1 000 000 EUR están exentas. El "
            "default para cualquier perfil autónomo es la exención."
        ),
    ),
    caps_into=None,
    related_modelos=(),
    submission_portal=Portal.PORTAL_M840_IAE,
    known_gotchas=(
        "Default-exento para todo autónomo persona física.",
        "TRLHL arts 78-91 no disponibles en corpus on-disk.",
    ),
)
