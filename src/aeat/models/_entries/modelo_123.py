"""Modelo 123 — retenciones sobre determinados rendimientos del capital mobiliario."""

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
    code=ModeloCode.MODELO_123,
    official_name_es=("Retenciones e ingresos a cuenta. Determinados rendimientos del capital mobiliario"),
    display_label={
        "es": ("Retenciones e ingresos a cuenta. Determinados rendimientos del capital mobiliario"),
        "en": "Withholdings on certain movable-capital income",
        "hu": "Egyes tőkejövedelmek forrásadója",
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
        mandatory=(),
        optional=(TaxpayerProfile.SL,),
        trigger_notes_es=(
            "Obligatorio en la práctica para sociedades que pagan dividendos o intereses. "
            "Fuera de alcance para autónomos ED en v1."
        ),
    ),
    caps_into=ModeloCode.MODELO_193,
    related_modelos=(ModeloCode.MODELO_193,),
    submission_portal_hint="Sede Electrónica AEAT — Modelo 123",
    known_gotchas=("RIRPF arts 74-76 no disponibles en corpus on-disk.",),
)
