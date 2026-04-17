"""Modelo 111 — retenciones IRPF trabajo y actividades."""

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
    code=ModeloCode.MODELO_111,
    official_name_es=("Retenciones e ingresos a cuenta del IRPF. Rendimientos del trabajo y de actividades económicas"),
    display_label={
        "es": ("Retenciones e ingresos a cuenta del IRPF. Rendimientos del trabajo y de actividades económicas"),
        "en": "IRPF withholdings on employment and professional fees",
        "hu": "IRPF forrásadó (munkabérek és szabadfoglalkozású díjak)",
    },
    category=ModeloCategory.RETENCIONES,
    cadence=ModeloCadence.QUARTERLY,
    legal_basis=(
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "80",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a80",
            "Fija los tipos aplicables al cálculo de retenciones e ingresos a cuenta sobre "
            "rendimientos del trabajo y establece las reglas de cálculo de la base de "
            "retención y del tipo de retención.",
        ),
        make_citation(
            LegalCitationSource.REAL_DECRETO,
            "95",
            "https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820#a95",
            "Establece los tipos fijos de retención aplicables a los rendimientos de "
            "actividades profesionales, agrícolas, ganaderas y forestales, y a las "
            "actividades en estimación objetiva.",
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
        mandatory=(
            TaxpayerProfile.AUTONOMO_ED_CON_EMPLEADOS,
            TaxpayerProfile.AUTONOMO_ED_CON_PROFESIONALES,
            TaxpayerProfile.SL,
        ),
        optional=(TaxpayerProfile.AUTONOMO_EO,),
        trigger_notes_es=(
            "Obligatorio cuando el autónomo paga salarios o honorarios profesionales bajo "
            "retención; mapea a AutonomoProfile.has_employees o al pago de profesionales con "
            "retención."
        ),
    ),
    caps_into=ModeloCode.MODELO_190,
    related_modelos=(ModeloCode.MODELO_190,),
    submission_portal=Portal.PORTAL_M111_RETENCIONES_TRABAJO,
    known_gotchas=(
        "Períodos con cero actividad siguen exigiendo presentación; suspensión requiere "
        "modificación censal vía Modelo 036.",
    ),
)
