"""Human presentation of scenario inputs without changing calculation addresses.

Machine identity stays in the in-memory plan. It is not shipped in cells,
comments or document properties. Missing display authority is a refusal, never
an invitation to prettify an internal identifier.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal

from ....core.decimal.coercion import coerce_decimal
from ....core.i18n.render import lookup_translation, tr
from ....core.period import AD_HOC_PERIOD_CODE, Period
from ....domain.calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from ....domain.calculations.registry.binding_selector_utils import binding_row_set_selector
from ....domain.calculations.registry.binding_temporal import FilingYearOffset, TargetPeriodOffset
from ....domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ....domain.calculations.registry.form_context import resolve_form_context_field
from ....domain.calculations.registry.ledger_binding_selector_support import LedgerIncomeFact
from ....domain.calculations.registry.ledger_renta_income_bindings import LedgerRentaIncomeProvider
from ....domain.calculations.registry.modelo_localization import binding_locale_key
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.schema_references import LegalReference, SourceReference
from .engine import registry_sha
from .errors import CalcSheetsEngineError
from .number_formats import numeric_format
from .records import (
    SheetAdministrativeFrame,
    SheetAutoFilter,
    SheetCellAddress,
    SheetCellConstraint,
    SheetColumnWidth,
    SheetEvidenceFacet,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFrozenView,
    SheetHiddenRow,
    SheetNumberFormat,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetRowHeight,
    SheetStyledRange,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .template_source import WorkbookTemplateSource
from .theme import StyleRole
from .workbook_exclusions import formula_may_read_transport_cell, workbook_transport_controls


def guide_paragraph_height(text: str) -> int:
    """Fit wrapped prose in the shared guide's 110-character-wide column."""
    return max(44, 20 * ((len(text) + 99) // 100 + 1))


def _leaves(expression: FormulaExpression) -> set[str]:
    result = {v for v in (expression.binding, expression.date_binding, expression.parameter) if v}
    if expression.dispatch_table:
        result.update(expression.dispatch_table.values())
    for argument in expression.args:
        result.update(_leaves(argument))
    return result


def human_workbook[M: (SheetExportMetadata, SheetReviewMetadata)](
    plan: SheetExportPlan[M], snapshot: RegistrySnapshot
) -> SheetExportPlan[M]:
    """Replace technical support surfaces, preserving all data and formula cells."""
    if isinstance(plan.metadata, SheetReviewMetadata):
        raise CalcSheetsEngineError("human form presentation requires a verified scenario plan")
    if plan.human_presentation:
        raise CalcSheetsEngineError("human workbook is already projected")
    if plan.metadata.registry_sha != registry_sha(snapshot):
        raise CalcSheetsEngineError("human workbook snapshot does not match the calculation authority")
    return _project_human_workbook(
        plan,
        revision=snapshot.revision,
        modelo_id=str(snapshot.modelo.id),
        frame=snapshot.filing_period or plan.metadata.period,
        legal_catalogue=snapshot.legal,
        source_catalogue=snapshot.sources,
        identity_digest=plan.metadata.registry_sha,
    )


def human_template_preview(
    plan: SheetExportPlan[SheetTemplatePreviewMetadata], source: WorkbookTemplateSource
) -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    """Project a fictional template after checking its exact presentation identity."""
    if (
        plan.metadata.modelo_id != source.modelo_id
        or plan.metadata.revision_id != source.revision.id
        or plan.metadata.preview_year != source.preview_frame.filing_year
        or plan.metadata.preview_period != source.preview_frame.code
        or plan.metadata.template_digest != source.template_digest
    ):
        raise CalcSheetsEngineError("template source does not match workbook preview identity")
    return _project_human_workbook(
        plan,
        revision=source.revision,
        modelo_id=str(source.modelo_id),
        frame=source.preview_frame,
        legal_catalogue=source.legal,
        source_catalogue=source.sources,
        identity_digest=source.template_digest,
    )


def _project_human_workbook[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    *,
    revision: ModeloRevision,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    legal_catalogue: Mapping[str, LegalReference],
    source_catalogue: Mapping[str, SourceReference],
    identity_digest: str,
) -> SheetExportPlan[M]:
    """Shared presentation assembly; callers own production or preview admission."""
    if plan.human_presentation:
        raise CalcSheetsEngineError("human workbook is already projected")
    casillas = {c.id: c for c in revision.casillas}
    excluded = workbook_transport_controls(revision)
    if any(row.casilla_id in excluded for row in (*plan.evidence.contributor_rows, *plan.evidence.manual_entries)):
        raise CalcSheetsEngineError("workbook transport exclusion cannot discard recorded evidence")
    printed_boxes = {
        placement.casilla_id: placement.box_number
        for layout in revision.form_layouts
        for placement in layout.placements
    }
    labels: dict[str, str] = {}
    for form in revision.form_layouts:
        for page in form.pages:
            for section in page.sections:
                for block in section.blocks:
                    if isinstance(block, FormContextFieldBlock):
                        owner = resolve_form_context_field(revision, block)
                        heading = lookup_translation(block.heading_key, locale="es") or block.official_heading
                        if owner.binding is not None and heading:
                            labels.setdefault(owner.binding, heading)
    row_bindings = {column.binding for row_set in plan.row_sets for column in row_set.columns}
    for binding in revision.bindings:
        declared_label = lookup_translation(binding_locale_key(str(modelo_id), binding.id, "label"), locale="es")
        if declared_label:
            labels[binding.id] = declared_label
            continue
        if binding.id in labels:
            continue
        if isinstance(binding.provider, AfiliadoContributionProvider):
            target = casillas.get(binding.provider.target_casilla_id)
            if target is not None:
                labels[binding.id] = target.label
                continue
        selector = binding_row_set_selector(binding) if binding.id in row_bindings else None
        if selector is not None:
            heading = lookup_translation(f"sheets.detalle.headers.{selector.row_field}", locale="es")
            if heading:
                labels[binding.id] = heading
        owners = [c.label for c in casillas.values() if c.binding == binding.id]
        if owners:
            labels[binding.id] = " / ".join(dict.fromkeys(owners))
        elif isinstance(binding.provider, PreviousFilingProvider):
            provider = binding.provider
            keys = provider.source_casilla_ids or ((provider.source_casilla_id,) if provider.source_casilla_id else ())
            names = [
                key
                if key.isdigit()
                else casillas[key].label
                if provider.source_modelo == modelo_id and key in casillas
                else ""
                for key in keys
            ]
            if names and all(names):
                when = ""
                if isinstance(provider.temporal, FilingYearOffset):
                    when = f" · ejercicio {frame.filing_year + provider.temporal.years}"
                elif isinstance(provider.temporal, TargetPeriodOffset):
                    when = f" · desplazamiento de {provider.temporal.periods} períodos"
                else:
                    continue
                labels[binding.id] = f"Modelo {provider.source_modelo}{when} · casillas: " + ", ".join(names)
        elif isinstance(binding.provider, LedgerRentaIncomeProvider):
            labels[binding.id] = {
                LedgerIncomeFact.INGRESOS_INTEGROS_SUM: "Ingresos íntegros fiscalmente computables",
                LedgerIncomeFact.CASH_RECEIVED_SUM: "Cobros recibidos",
                LedgerIncomeFact.TAXABLE_BASE_SUM: "Base imponible de los ingresos",
                LedgerIncomeFact.DECLARED_WITHHELD_AMOUNT_SUM: "Retenciones declaradas en las facturas de ingresos",
            }[binding.provider.fact]
    consumers: dict[str, list[str]] = {}
    for formula in revision.formulas:
        for key in _leaves(formula.expression):
            consumers.setdefault(key, []).append(casillas[formula.target_casilla_id].label)
    for parameter in revision.parameters:
        owners = consumers.get(parameter.id, [])
        if owners:
            labels[parameter.id] = "Parámetro para: " + " / ".join(dict.fromkeys(owners))

    def label(key: str) -> str:
        if key not in labels:
            raise CalcSheetsEngineError(
                "human workbook requires an authored label for a calculation input",
                context={"reference": key},
            )
        return labels[key]

    def legal_text(refs: tuple[str, ...]) -> str:
        parts: list[str] = []
        for key in refs:
            reference = legal_catalogue.get(key)
            if reference is None:
                raise CalcSheetsEngineError("human workbook legal reference is missing")
            parts.append(
                reference.document_id
                + (f", artículo {reference.article}" if reference.article else "")
                + (f", {reference.section}" if reference.section else "")
                + f" — {reference.permalink}"
            )
        return "\n".join(dict.fromkeys(parts))

    def source_text(refs: tuple[str, ...]) -> str:
        parts: list[str] = []
        for key in refs:
            source = source_catalogue.get(key)
            if source is None:
                raise CalcSheetsEngineError("human workbook official source is missing")
            parts.append(str(source.source_url))
        return "\n".join(dict.fromkeys(parts))

    rows = {
        (c.address.tab, c.address.row): casillas[c.casilla_id]
        for c in (*plan.value_cells, *plan.formula_cells)
        if c.casilla_id in casillas and c.address.tab in (TabName.ENTRADAS, TabName.CALCULOS)
    }
    excluded_addresses = tuple(c.address for c in (*plan.value_cells, *plan.formula_cells) if c.casilla_id in excluded)
    if any(
        cell.casilla_id in excluded or formula_may_read_transport_cell(cell, excluded_addresses)
        for cell in plan.formula_cells
    ):
        raise CalcSheetsEngineError("workbook transport exclusion is referenced by a sheet formula")
    readonly_source_rows = {(c.address.tab, c.address.row) for c in plan.value_cells if c.role == "source_value"}
    anchors = {a.address.qualified() for a in plan.anchors}
    values: list[SheetValueCell] = []
    for cell in plan.value_cells:
        address = cell.address
        owner = rows.get((address.tab, address.row))
        if owner is not None and owner.id in excluded:
            continue
        if address.tab in (TabName.PROVENANCE, TabName.GUIDE, TabName.EVIDENCIA) or address.qualified() in anchors:
            if cell.role not in ("label", "metadata"):
                raise CalcSheetsEngineError("human presentation cannot discard a data cell")
            continue
        value = cell.value
        if cell.role == "label":
            if address.tab in (TabName.ENTRADAS, TabName.CALCULOS):
                if address.row == 1:
                    value = ("Origen", "Casilla", "Concepto", "Valor")[address.column - 1]
                elif address.column == 1:
                    value = (
                        "Dato de origen"
                        if (address.tab, address.row) in readonly_source_rows
                        else "Dato de entrada"
                        if address.tab is TabName.ENTRADAS
                        else "Cálculo"
                    )
                elif address.column == 2:
                    owner = rows.get((address.tab, address.row))
                    # Registry `number` can be a record byte position. The
                    # authored placement owns the human form's printed box.
                    value = (printed_boxes.get(owner.id, owner.form_number) or "") if owner else ""
                elif address.column == 3 and isinstance(value, str) and value in {b.id for b in revision.bindings}:
                    value = label(value)
            elif address.tab is TabName.TARIFFS:
                if cell.parameter:
                    value = label(cell.parameter)
                elif isinstance(value, str) and value in {b.id for b in revision.bindings}:
                    value = label(value)
                else:
                    value = {
                        "Minimum base": "Base mínima",
                        "Maximum base": "Base máxima",
                        "Fixed quota": "Cuota fija",
                        "Marginal rate": "Tipo marginal",
                    }.get(str(value), value)
        values.append(cell.model_copy(update={"value": value}))

    def emit(tab: TabName, row: int, items: tuple[str | Decimal | bool | None, ...]) -> None:
        for column, value in enumerate(items, 1):
            values.append(SheetValueCell(address=SheetCellAddress.at(tab, row, column), value=value, role="label"))

    period_suffix = f" · {frame.code}" if isinstance(frame, Period) and frame.code != AD_HOC_PERIOD_CODE else ""
    preview_guide = isinstance(plan.metadata, SheetTemplatePreviewMetadata)
    emit(
        TabName.GUIDE,
        1,
        (plan.guide.title if preview_guide else f"Modelo {modelo_id} · {frame.filing_year}{period_suffix}",),
    )
    emit(TabName.GUIDE, 3, ("Documento de trabajo. No acredita la presentación de una declaración.",))
    emit(
        TabName.GUIDE,
        4,
        (
            "Edite los datos en Entradas. Modelo muestra el resultado; Cálculos y Tarifas permiten revisarlo."
            if isinstance(frame, Period)
            else tr("application.storage.calc_sheets.form.communication_guide", locale="es"),
        ),
    )
    emit(
        TabName.GUIDE,
        5,
        ("Una celda vacía es un dato pendiente. Complete los datos necesarios antes de utilizar el resultado.",),
    )
    # Preview authors supply the example's assumptions and calculation limits.
    # Keep them in the transport cells, subject to the technical-text guard below.
    if preview_guide:
        for row, paragraph in enumerate(plan.guide.paragraphs, 7):
            emit(TabName.GUIDE, row, (paragraph,))

    emit(TabName.PROVENANCE, 1, ("Concepto", "Normativa", "Fuente oficial"))
    refs: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
        (c.label, tuple(c.legal_refs), tuple(c.source_refs))
        for c in casillas.values()
        if c.id not in excluded and not c.internal_only
    ]
    refs.extend(
        (labels[p.id], tuple(p.legal_refs), tuple(p.source_refs)) for p in revision.parameters if p.id in labels
    )
    refs.extend((labels[b.id], tuple(b.legal_refs), tuple(b.source_refs)) for b in revision.bindings if b.id in labels)
    refs.extend(
        (casillas[f.target_casilla_id].label, tuple(f.legal_refs), tuple(f.source_refs))
        for f in revision.formulas
        if not casillas[f.target_casilla_id].internal_only
    )
    for index, (name, legal, sources) in enumerate(refs, 2):
        emit(TabName.PROVENANCE, index, (name, legal_text(legal), source_text(sources)))

    emit(
        TabName.EVIDENCIA,
        1,
        (
            "Concepto",
            "Importe",
            "Moneda",
            "Base imponible",
            "Tipo IVA",
            "Cuota IVA",
            "Contraparte",
            "Cambio a euros",
            "Importe en euros",
            "Valor declarado",
            "Normativa",
            "Fuente oficial",
            "Origen del dato",
            "Explicación",
        ),
    )
    evidence_formats: list[SheetNumberFormat] = []

    def evidence_format(row: int, column: int, kind: str, currency: str | None = "EUR") -> None:
        pattern = numeric_format(kind, currency=currency)
        if pattern is not None:
            evidence_formats.append(
                SheetNumberFormat(
                    address=SheetCellAddress.at(TabName.EVIDENCIA, row, column),
                    data_type=pattern[0],
                    pattern=pattern[1],
                )
            )

    for index, row in enumerate(plan.evidence.contributor_rows, 2):
        if row.attachment_ids or row.document_link_ids:
            raise CalcSheetsEngineError("human evidence requires resolved document references")
        evidence_format(index, 2, "money", row.currency)
        for column, kind in ((4, "money"), (5, "ratio"), (6, "money"), (8, "decimal"), (9, "money")):
            evidence_format(index, column, kind, "EUR" if column == 9 else row.currency)
        emit(
            TabName.EVIDENCIA,
            index,
            (
                casillas[row.casilla_id].label,
                row.amount,
                row.currency,
                row.taxable_base,
                row.iva_rate,
                row.iva_amount,
                row.counterparty,
                row.fx_rate,
                row.value_in_eur,
                None,
                legal_text(row.legal_refs),
                source_text(row.source_refs),
                "Movimiento registrado",
                None,
            ),
        )
    for index, row in enumerate(plan.evidence.manual_entries, 2 + len(plan.evidence.contributor_rows)):
        kind_labels = {"casilla_input": "Dato introducido", "binding_override": "Dato sustituido por el usuario"}
        if row.kind not in kind_labels:
            raise CalcSheetsEngineError("human evidence requires an authored fact-kind label")
        evidence_format(index, 10, casillas[row.casilla_id].data_type)
        displayed_value: str | Decimal = row.value
        if numeric_format(casillas[row.casilla_id].data_type) is not None:
            parsed = coerce_decimal(row.value)
            if parsed is not None and parsed.is_finite():
                displayed_value = parsed
        emit(
            TabName.EVIDENCIA,
            index,
            (
                casillas[row.casilla_id].label,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                displayed_value,
                legal_text(row.legal_refs),
                source_text(row.source_refs),
                kind_labels[row.kind],
                row.note,
            ),
        )

    constraints: list[SheetCellConstraint] = []
    for constraint in plan.cell_constraints:
        if constraint.casilla_id in excluded:
            continue
        lower, upper = constraint.resolved_bounds()
        bounds = " y ".join(
            part
            for part in (f"mínimo {lower}" if lower is not None else "", f"máximo {upper}" if upper is not None else "")
            if part
        )
        if constraint.allowed_values is not None:
            choices = "valores admitidos: " + ", ".join(constraint.allowed_values)
            bounds = f"{bounds}; {choices}" if bounds else choices
        for length, description in (
            (constraint.min_length, "longitud mínima"),
            (constraint.max_length, "longitud máxima"),
        ):
            if length is not None:
                limit = f"{description}: {length} caracteres"
                bounds = f"{bounds}; {limit}" if bounds else limit
        constraints.append(
            constraint.model_copy(
                update={
                    "presentation_message": (
                        f"{casillas[constraint.casilla_id].label}: {bounds or 'sin límite numérico'}. "
                        f"{legal_text(constraint.legal_refs)}"
                    )
                }
            )
        )
    row_sets = tuple(
        row_set.model_copy(
            update={
                "columns": tuple(
                    column.model_copy(update={"header_label": label(column.binding)}) for column in row_set.columns
                )
            }
        )
        for row_set in plan.row_sets
    )
    internal_tokens = (
        {b.id for b in revision.bindings} | {p.id for p in revision.parameters} | {f.id for f in revision.formulas}
    )
    for cell in values:
        for text in (cell.value if cell.role in ("label", "metadata") else None, cell.note):
            if isinstance(text, str) and (
                re.search(r"\b[0-9a-f]{64}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", text, re.I)
                or any(token in text for token in internal_tokens)
                or identity_digest in text
                or (
                    isinstance(plan.metadata, (SheetExportMetadata, SheetTemplatePreviewMetadata))
                    and plan.metadata.engine_version == text
                )
            ):
                raise CalcSheetsEngineError(
                    "human workbook contains unresolved technical presentation text",
                    context={"cell": cell.address.qualified()},
                )
    replaced_tabs = (TabName.GUIDE, TabName.PROVENANCE, TabName.EVIDENCIA)
    sizes = {
        tab: (
            max(cell.address.row for cell in values if cell.address.tab is tab),
            max(cell.address.column for cell in values if cell.address.tab is tab),
        )
        for tab in replaced_tabs
    }
    widths = {
        TabName.GUIDE: (110,),
        TabName.PROVENANCE: (65, 80, 80),
        TabName.EVIDENCIA: (60, 15, 10, 15, 12, 15, 35, 15, 18, 20, 70, 70, 30, 60),
    }
    styles = tuple(
        style
        for tab, (last_row, last_column) in sizes.items()
        for style in (
            SheetStyledRange(
                tab=tab,
                start_row=1,
                end_row=last_row,
                start_column=1,
                end_column=last_column,
                role=StyleRole.FORM_LABEL,
                wrap=True,
            ),
            SheetStyledRange(
                tab=tab,
                start_row=1,
                end_row=1,
                start_column=1,
                end_column=last_column,
                role=StyleRole.FORM_SECTION,
                wrap=True,
            ),
        )
    )
    return type(plan).model_validate(
        {
            **dict(plan),
            "human_presentation": True,
            "hidden_rows": tuple(
                SheetHiddenRow(tab=tab, row=row)
                for tab, row in sorted(
                    {(hidden.tab, hidden.row) for hidden in plan.hidden_rows if hidden.tab not in replaced_tabs}
                    | {address for address, owner in rows.items() if owner.internal_only}
                )
            ),
            "value_cells": tuple(values),
            "cell_constraints": tuple(constraints),
            "row_sets": row_sets,
            "anchors": (),
            "section_headers": (),
            "evidence": SheetEvidenceFacet(),
            "protected_ranges": (
                *(
                    region.model_copy(update={"description": "Datos calculados y referencias de consulta"})
                    for region in plan.protected_ranges
                    if region.tab not in replaced_tabs
                ),
                *(
                    SheetProtectedRange(
                        tab=tab,
                        start_row=1,
                        end_row=last_row,
                        start_column=1,
                        end_column=last_column,
                        description="Datos y referencias de consulta",
                    )
                    for tab, (last_row, last_column) in sizes.items()
                ),
            ),
            "auto_filters": (
                *(region for region in plan.auto_filters if region.tab not in replaced_tabs),
                *(
                    SheetAutoFilter(tab=tab, start_row=1, end_row=last_row, start_column=1, end_column=last_column)
                    for tab, (last_row, last_column) in sizes.items()
                    if tab is not TabName.GUIDE
                ),
            ),
            "frozen_views": (
                *(view for view in plan.frozen_views if view.tab not in replaced_tabs),
                *(SheetFrozenView(tab=tab, frozen_rows=1) for tab in replaced_tabs),
            ),
            "column_widths": (
                *(width for width in plan.column_widths if width.tab not in replaced_tabs),
                *(
                    SheetColumnWidth(tab=tab, column=column, width=width)
                    for tab, columns in widths.items()
                    for column, width in enumerate(columns, 1)
                ),
            ),
            "styled_ranges": (*(style for style in plan.styled_ranges if style.tab not in replaced_tabs), *styles),
            "merged_ranges": tuple(region for region in plan.merged_ranges if region.tab not in replaced_tabs),
            "row_heights": (
                *(height for height in plan.row_heights if height.tab not in replaced_tabs),
                *(
                    SheetRowHeight(
                        tab=TabName.GUIDE,
                        row=cell.address.row,
                        height_pixels=guide_paragraph_height(str(cell.value)),
                    )
                    for cell in values
                    if cell.address.tab is TabName.GUIDE
                ),
            ),
            "number_formats": (
                *(fmt for fmt in plan.number_formats if fmt.address.tab not in replaced_tabs),
                *evidence_formats,
            ),
        }
    )
