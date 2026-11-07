"""Fictional refund examples use current or explicit historical template authority."""

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
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from .compiler.authority import compiled_bundled_authority
from .workbook_demo_cases import newest_historical_year, template_edition
from .workbook_template_source import load_workbook_template_source


def refund_inputs(year: int, *, historical: bool = False) -> OperatorInputs:
    """Declared fictional facts; the registry owns all financial formulas."""
    values: dict[str, Decimal | str] = {
        "decl.ejercicio": Decimal(year),
        "decl.nombre": "Ana",
        "decl.tipo-declaracion": "D",
        "papel-importe-devolucion": Decimal("250.35"),
        "decl.tipo-tributacion": "2",
        "decl.req-base-08": Decimal("1001.19"),
        "decl.req-tipo-09": Decimal("21"),
        "decl.req-cuota-10": Decimal("210.25"),
        "decl.req-base-11": Decimal("401"),
        "decl.req-tipo-12": Decimal("10"),
        "decl.req-cuota-13": Decimal("40.10"),
        "decl.req-base-14": Decimal("0"),
        "decl.req-tipo-15": Decimal("4"),
        "decl.req-cuota-16": Decimal("0"),
    }
    if historical:
        values.update({"papel-nif": "12345678Z", "papel-apellidos": "Ejemplo"})
    return OperatorInputs(values=tuple(OperatorInput(casilla_id=k, value=v) for k, v in values.items()))


def build_historical_refund_plan(
    *, year: int | None = None
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Build an evidenced historical example without widening filing support."""
    year = newest_historical_year("308") if year is None else year
    edition = template_edition("308", year)
    source = load_workbook_template_source(
        "308",
        revision_id=edition.revision_id,
        source_ref=edition.source_ref,
        preview_year=year,
        preview_period=edition.period,
    )
    inputs = refund_inputs(year, historical=True)
    if not any(str(item.id) == "decl.nombre" for item in source.revision.casillas):
        inputs = OperatorInputs(
            values=(
                *(
                    item
                    for item in inputs.values
                    if item.casilla_id not in {"decl.nombre", "decl.tipo-tributacion", "papel-apellidos"}
                ),
                OperatorInput(casilla_id="papel-nombre-completo", value="Ana Ejemplo"),
            )
        )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(
            source,
            operator_inputs=inputs,
            guide=SheetGuideContent(
                title=f"Modelo 308 de {year} · Ejemplo ficticio",
                paragraphs=(
                    "Vista histórica con datos ficticios. "
                    "No constituye una solicitud presentada ni habilita su presentación.",
                ),
            ),
        )
        plan = add_template_preview_form(plan, source)
    return source, plan
