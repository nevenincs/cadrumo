"""Fictional detail rows through each parallel Modelo 369 registry template."""

from decimal import Decimal
from typing import Literal

from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_template_preview_form
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import (
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
)
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.schema_form_layouts import FormGridBlock

from .compiler.authority import compiled_bundled_authority
from .workbook_template_source import load_workbook_template_source


def build_oss_detail_plan(
    *, scheme: Literal["exterior", "union", "importacion"], year: int = 2025
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Populate authored grid owners; never invent a country settlement formula."""
    period = {"exterior": "EXT-1T", "union": "1T", "importacion": "01"}[scheme]
    source = load_workbook_template_source(
        "369",
        revision_id=f"esquema-{scheme}",
        source_ref="boe-modelo-369-2021-original-form-pdf",
        preview_year=year,
        preview_period=period,
    )
    names = {"exterior": "Régimen exterior", "union": "Régimen de la Unión", "importacion": "Importación"}
    grids = tuple(
        block
        for form in source.revision.form_layouts
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock) and block.id != "resultado-estados"
    )
    populated_rows = 1 if scheme == "union" else 2
    unused_rows = {grid.id: tuple(row.key for row in grid.rows[populated_rows:]) for grid in grids}
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(
            source,
            unused_example_rows=unused_rows,
            guide=SheetGuideContent(
                title=f"Modelo 369 · {names[scheme]} · {year} · Ejemplo ficticio parcial",
                paragraphs=(
                    "Importes ficticios para revisar las tablas de operaciones y correcciones.",
                    "Las bases y cuotas son entradas independientes: cambiar una base no recalcula su cuota. "
                    "Los tipos usados ilustran el diseño y no determinan el tipo aplicable a una operación real.",
                    (
                        "Alemania: cuota de 190 euros menos una corrección de 20 euros: ingreso de 170 euros. "
                        "Francia: cuota de 100 euros menos una corrección de 140 euros: devolución de 40 euros. "
                        "La devolución francesa no reduce el ingreso de 170 euros en España. "
                        "En este ejemplo, las demás filas de operaciones y correcciones están expresamente sin usar."
                        if scheme != "union"
                        else "Alemania: 190 euros de servicios y 190 euros de bienes desde España, "
                        "más 190 euros de servicios y 380 euros de bienes desde otros Estados miembros. "
                        "La cuota de 950 euros menos una corrección de 20 euros da un ingreso de 930 euros. "
                        "En este ejemplo, las demás filas de operaciones y correcciones están expresamente sin usar."
                    ),
                    "Falta el ingreso adicional. Los subtotales parciales no son el importe a ingresar. "
                    "La identidad y los datos no aportados permanecen sin dato.",
                ),
            ),
        )
        layout = plan_layout(source.revision)
        values = {}
        for grid in grids:
            # Different amounts expose accidental mixing of the Union's two
            # other-member-state flows, a defect in the former generated layout.
            base = Decimal("2000") if grid.id == "union-envio" else Decimal("1000")
            example: dict[str, Decimal | str] = {
                "pais-consumo": "DE",
                "pais-origen": "FR",
                "niva": "FR-EJEMPLO",
                "tipo": Decimal("19"),
                "clase": "S",
                "base": base,
                "cuota": base * Decimal("0.19"),
                "ejercicio": Decimal(year - 1),
                "tipo-periodo": "M" if scheme == "importacion" else "T",
                "periodo": "12" if scheme == "importacion" else "4T",
                "correccion": Decimal("-20"),
            }
            examples = [example]
            if scheme != "union":
                examples.append(
                    {
                        **example,
                        "pais-consumo": "FR",
                        "tipo": Decimal("20"),
                        "base": Decimal("500"),
                        "cuota": Decimal("100"),
                        "correccion": Decimal("-140"),
                    }
                )
            for row, row_values in zip(grid.rows[: len(examples)], examples, strict=True):
                for column, cell in zip(grid.columns, row.cells, strict=True):
                    if cell.binding_id is None:
                        raise ValueError("OSS detail example requires an exact declared binding owner")
                    values[layout.binding_cells[cell.binding_id]] = row_values[column.key]
        cells = tuple(
            cell.model_copy(update={"value": values[cell.address]}) if cell.address in values else cell
            for cell in plan.value_cells
        )
        plan = SheetExportPlan[SheetTemplatePreviewMetadata].model_validate({**dict(plan), "value_cells": cells})
        return source, add_template_preview_form(plan, source)
