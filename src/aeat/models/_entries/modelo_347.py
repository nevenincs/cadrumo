"""Modelo 347 — declaración anual de operaciones con terceras personas."""

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
    code=ModeloCode.MODELO_347,
    official_name_es="Declaración anual de operaciones con terceras personas",
    display_label={
        "es": "Declaración anual de operaciones con terceras personas",
        "en": "Annual information return — third-party transactions",
        "hu": "Éves adatszolgáltatás harmadik felekkel folytatott ügyletekről",
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
            "29",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a29",
            "Enumera las obligaciones tributarias formales, incluida la presentación de "
            "declaraciones, autoliquidaciones y comunicaciones, la llevanza de libros y "
            "registros y la expedición y conservación de facturas.",
        ),
    ),
    applicability=build_applicability(
        mandatory=(),
        optional=tuple(TaxpayerProfile),
        trigger_notes_es=(
            "Obligatorio para contribuyentes con operaciones con un mismo tercero superiores "
            "a 3 005,06 EUR (IVA incluido). Los obligados a SII quedan exentos. Default "
            "opcional; se convierte en obligatorio una vez superado el umbral."
        ),
    ),
    caps_into=None,
    related_modelos=(),
    submission_portal=Portal.PORTAL_M347_OPERACIONES_TERCEROS,
    known_gotchas=(
        "Reglas de exclusión complejas.",
        "Los obligados a SII están exentos.",
    ),
)
