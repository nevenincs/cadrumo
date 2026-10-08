"""Historical Modelo 309 example using the registry and shared preview compiler."""

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_template_preview_form
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInput,
    OperatorInputs,
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
)
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from .compiler.authority import compiled_bundled_authority
from .workbook_demo import DemoCase, demonstration_producer
from .workbook_demo_nonperiodic import nonperiodic_vat_inputs
from .workbook_template_source import load_workbook_template_source


def build_historical_nonperiodic_plan(
    *, year: int = 2016
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Build fictional historical facts without extending the filing support envelope."""
    revision_id, source_ref = {2015: ("2004-2015", "aeat-dr-309-2004"), 2016: ("2016-2017", "aeat-dr-309-2016")}[year]
    source = load_workbook_template_source(
        "309", revision_id=revision_id, source_ref=source_ref, preview_year=year, preview_period="AD-HOC"
    )
    case = DemoCase(
        "309",
        revision_id,
        "decl.resultado-24",
        Decimal("210"),
        filing_year=year,
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        period="AD-HOC",
    )
    inputs = nonperiodic_vat_inputs(year, additional_rate_row=False)
    if year == 2015:
        # The original record has independent X-or-blank fields, not numeric selectors.
        values = {item.casilla_id: item.value for item in inputs.values}
        for cid in (
            "decl.nombre",
            "decl.tipo-declaracion",
            "decl.situacion-tributaria",
            "decl.hecho-imponible",
            "decl.transmitente-apellidos",
            "decl.transmitente-pais",
        ):
            del values[cid]
        values.update(
            {
                "decl.periodo": "1T",
                "papel-nombre-completo": "Ana Ejemplo",
                "papel-complementaria": False,
                "wire.transmitente-apellidos-nombre-razon-social": "Vehículos Ejemplo",
                "wire.transmitente-pais-texto": "Francia",
                "decl.situacion-tributaria-persona-fisica-no-empresario": "X",
                "decl.hecho-imponible-medios-transporte-nuevos": "X",
            }
        )
        inputs = OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in values.items()))
    address = {
        "papel-domicilio-tipo-via": "Calle",
        "papel-domicilio-via": "Ejemplo ficticio",
        "papel-domicilio-numero": "10",
        "papel-domicilio-codigo-postal": "28001",
        "papel-domicilio-municipio": "Madrid",
        "papel-domicilio-provincia": "Madrid",
    }
    inputs = OperatorInputs(
        values=(*inputs.values, *(OperatorInput(casilla_id=k, value=v) for k, v in address.items()))
    )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(
            source,
            operator_inputs=inputs,
            guide=SheetGuideContent(
                title=f"Modelo 309 de {year} · Ejemplo ficticio",
                paragraphs=(
                    "Vista histórica con identidad y domicilio ficticios. No es una declaración presentada.",
                    "Bases, tipos y cuotas por fila son datos introducidos. Los totales 22 y 24 se recalculan.",
                    "La copia del resultado en Ingreso no acredita un pago. Cuenta bancaria y firma quedan sin dato.",
                ),
            ),
        )
        plan = add_template_preview_form(plan, source, illustrative_producer=demonstration_producer(case))
    return source, plan
