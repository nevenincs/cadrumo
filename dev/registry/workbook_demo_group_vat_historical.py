"""Historical Modelo 322 examples compiled from the actual registry templates."""

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
from .workbook_demo_group_vat import group_vat_inputs
from .workbook_template_source import load_workbook_template_source


def build_historical_group_vat_plan(
    *, year: int
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Use fictional December facts; the shared compiler owns positions and formulas."""
    revision_id, source_ref = {
        2022: ("2008-2022", "aeat-dr-322-2022"),
        2023: ("2023", "aeat-dr-322-2023"),
        2025: ("2024-2025", "aeat-dr-322-2024-2025"),
    }[year]
    source = load_workbook_template_source(
        "322", revision_id=revision_id, source_ref=source_ref, preview_year=year, preview_period="12"
    )
    casillas = {casilla.id: casilla for casilla in source.revision.casillas}
    inputs = OperatorInputs(
        values=tuple(
            OperatorInput(
                casilla_id=item.casilla_id,
                value="1" if item.casilla_id == "decl.prorrata-especial" else item.value,
            )
            for item in group_vat_inputs(year, "12").values
            if item.casilla_id in casillas and casillas[item.casilla_id].formula is None
        )
    )
    case = DemoCase(
        "322",
        revision_id,
        "70",
        Decimal("1650"),
        filing_year=year,
        authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        period="12",
    )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(
            source,
            operator_inputs=inputs,
            guide=SheetGuideContent(
                title=f"Modelo 322 · Diciembre {year} · Ejemplo ficticio",
                paragraphs=(
                    "Datos ficticios para comprobar el formulario. No es una declaración presentada.",
                    "Las bases, tipos y cuotas por fila son datos introducidos. Los totales se recalculan.",
                    "Los datos desconocidos permanecen sin dato; un resultado cero no significa ausencia de actividad.",
                ),
            ),
        )
        plan = add_template_preview_form(plan, source, illustrative_producer=demonstration_producer(case))
    return source, plan
