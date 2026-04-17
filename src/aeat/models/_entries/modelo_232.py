"""Modelo 232 — operaciones vinculadas y paraísos fiscales."""

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
    code=ModeloCode.MODELO_232,
    official_name_es=(
        "Declaración informativa de operaciones vinculadas y de operaciones y situaciones "
        "relacionadas con países o territorios calificados como paraísos fiscales"
    ),
    display_label={
        "es": (
            "Declaración informativa de operaciones vinculadas y de operaciones y "
            "situaciones relacionadas con países o territorios calificados como paraísos "
            "fiscales"
        ),
        "en": "Information return — related-party and tax-haven transactions",
        "hu": "Kapcsolt felekkel és adóparadicsomokkal folytatott ügyletek adatszolgáltatása",
    },
    category=ModeloCategory.INFORMATIVA,
    cadence=ModeloCadence.ANNUAL,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "30",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984#a30",
            "Desarrolla las obligaciones de presentación de declaraciones informativas por "
            "parte de los obligados tributarios; umbrella reglamentaria del Modelo 232.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Solo aplica a sociedades (SL) con operaciones vinculadas por encima del umbral de 250 000 EUR."
        ),
    ),
    caps_into=None,
    related_modelos=(ModeloCode.MODELO_200,),
    submission_portal=Portal.PORTAL_M232_VINCULADAS,
    known_gotchas=("Solo aplicable a SL; candidato a aplazamiento.",),
)
