"""Render the guide, provenance and evidence workbook tabs."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ....core.decimal.coercion import coerce_decimal
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .errors import CalcSheetsEngineError
from .number_formats import numeric_format
from .records import (
    SheetAdministrativeFrame,
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    TabName,
)

Emit = Callable[[TabName, int, tuple[str | Decimal | bool | None, ...]], None]
ReferenceText = Callable[[tuple[str, ...]], str]


def render_guide[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M], modelo_id: str, frame: Period | SheetAdministrativeFrame, emit: Emit
) -> None:
    """Render guide cells for a scenario or a preview."""
    period_suffix = f" · {frame.code}" if isinstance(frame, Period) else ""
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


def _input_references(
    revision: ModeloRevision, labels: dict[str, str]
) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    refs = [(labels[p.id], tuple(p.legal_refs), tuple(p.source_refs)) for p in revision.parameters if p.id in labels]
    refs.extend((labels[b.id], tuple(b.legal_refs), tuple(b.source_refs)) for b in revision.bindings if b.id in labels)
    return refs


def render_provenance(
    revision: ModeloRevision,
    casillas: dict[str, CasillaDefinition],
    excluded: frozenset[str],
    labels: dict[str, str],
    emit: Emit,
    legal_text: ReferenceText,
    source_text: ReferenceText,
) -> None:
    """Render authored legal and source references.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    emit(TabName.PROVENANCE, 1, ("Concepto", "Normativa", "Fuente oficial"))
    refs: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
        (c.label, tuple(c.legal_refs), tuple(c.source_refs))
        for c in casillas.values()
        if c.id not in excluded and not c.internal_only
    ]
    refs.extend(_input_references(revision, labels))
    refs.extend(
        (casillas[f.target_casilla_id].label, tuple(f.legal_refs), tuple(f.source_refs))
        for f in revision.formulas
        if not casillas[f.target_casilla_id].internal_only
    )
    for index, (name, legal, sources) in enumerate(refs, 2):
        emit(TabName.PROVENANCE, index, (name, legal_text(legal), source_text(sources)))


def _manual_value(value: str, data_type: str) -> str | Decimal:
    if numeric_format(data_type) is not None:
        parsed = coerce_decimal(value)
        if parsed is not None and parsed.is_finite():
            return parsed
    return value


def render_evidence[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    casillas: dict[str, CasillaDefinition],
    emit: Emit,
    legal_text: ReferenceText,
    source_text: ReferenceText,
) -> list[SheetNumberFormat]:
    """Render evidence rows and return their numeric formats."""
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
        displayed_value = _manual_value(row.value, casillas[row.casilla_id].data_type)
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

    return evidence_formats
