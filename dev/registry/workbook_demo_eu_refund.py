"""Fictional 360 application through the registry-owned workbook compiler."""

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
from .workbook_template_source import load_workbook_template_source


def build_eu_refund_plan(
    *, year: int = 2025
) -> tuple[WorkbookTemplateSource, SheetExportPlan[SheetTemplatePreviewMetadata]]:
    """Declare two invoices without inventing refund eligibility or a bank account."""
    source = load_workbook_template_source(
        "360",
        revision_id="2010-y-siguientes",
        source_ref="boe-modelo-360-2010-original-form-pdf",
        preview_year=year,
        preview_period="AD-HOC",
    )
    values: dict[str, Decimal | str] = {
        "decl.ejercicio": Decimal(year),
        "decl.estado-miembro": "DE",
        "decl.solicitante-email": "ejemplo@example.invalid",
        "decl.solicitante.direccion.tipo-via": "CL",
        "decl.solicitante.direccion.nombre-via": "Ejemplo ficticio",
        "decl.solicitante.direccion.numero-casa": "10",
        "decl.solicitante.direccion.codigo-postal": "08001",
        "decl.solicitante.direccion.municipio": "Barcelona",
        "devolucion.importe-solicitado": Decimal("285"),
        "devolucion.divisa": "EUR",
        "devolucion.numero-facturas": Decimal("2"),
        "devolucion.numero-documentos-importacion": Decimal("0"),
        "devolucion.periodo-fecha-inicio": f"{year}-01-01",
        "devolucion.periodo-fecha-fin": f"{year}-12-31",
    }
    for n, base, vat in ((1, "1000", "190"), (2, "500", "95")):
        prefix = f"decl.op{n}-"
        values.update(
            {
                prefix + "numero": str(n),
                prefix + "factura": f"EJEMPLO-{year}-{n:03}",
                prefix + "fecha": f"{year}-06-{n:02}",
                prefix + "base": Decimal(base),
                prefix + "cuota": Decimal(vat),
                prefix + "prorrata": Decimal("100"),
                prefix + "importe": Decimal(vat),
                prefix + "divisa": "EUR",
                prefix + "proveedor-nombre": f"Proveedor ficticio {n}",
                prefix + "proveedor-pais": "DE",
            }
        )
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(
            source,
            operator_inputs=OperatorInputs(
                values=tuple(OperatorInput(casilla_id=key, value=value) for key, value in values.items())
            ),
            guide=SheetGuideContent(
                title=f"Modelo 360 · {year} · Ejemplo ficticio",
                paragraphs=(
                    "Dos facturas ficticias con bases de 1.000 y 500 euros y cuotas declaradas de 190 y 95 euros.",
                    "Se solicitan 285 euros. Bases, cuotas, prorratas y total son entradas independientes: "
                    "el registro no define fórmulas para recalcularlos al editar una factura.",
                    "La prorrata del 100 % es un supuesto ilustrativo; no acredita el derecho a devolución. "
                    "La naturaleza de los gastos y los códigos no aportados quedan sin dato.",
                    "La identidad fiscal y la cuenta bancaria permanecen sin dato. "
                    "No se construye una solicitud de presentación sin los datos bancarios obligatorios.",
                    "Este ejemplo no constituye una solicitud presentada ni determina el IVA recuperable.",
                ),
            ),
        )
        plan = add_template_preview_form(plan, source)
    return source, plan
