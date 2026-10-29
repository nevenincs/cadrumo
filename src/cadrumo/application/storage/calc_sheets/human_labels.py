"""Resolve authored labels for human workbook calculation inputs."""

from __future__ import annotations

from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from ....domain.calculations.registry.binding_selector_utils import binding_row_set_selector
from ....domain.calculations.registry.binding_temporal import FilingYearOffset, TargetPeriodOffset
from ....domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ....domain.calculations.registry.form_context import resolve_form_context_field
from ....domain.calculations.registry.ledger_binding_selector_support import LedgerIncomeFact
from ....domain.calculations.registry.ledger_renta_income_bindings import LedgerRentaIncomeProvider
from ....domain.calculations.registry.modelo_localization import binding_locale_key
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .records import (
    SheetAdministrativeFrame,
    SheetExportMetadata,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
)


def _leaves(expression: FormulaExpression) -> set[str]:
    result = {v for v in (expression.binding, expression.date_binding, expression.parameter) if (v is not None and v)}
    if expression.dispatch_table is not None and expression.dispatch_table:
        result.update(expression.dispatch_table.values())
    for argument in expression.args:
        result.update(_leaves(argument))
    return result


def _add_form_label(revision: ModeloRevision, block: FormContextFieldBlock, labels: dict[str, str]) -> None:
    owner = resolve_form_context_field(revision, block)
    heading = lookup_translation(block.heading_key, locale="es") or block.official_heading
    if owner.binding is not None and heading is not None and heading:
        labels.setdefault(owner.binding, heading)


def _form_labels(revision: ModeloRevision) -> dict[str, str]:
    labels: dict[str, str] = {}
    blocks = (
        block
        for form in revision.form_layouts
        for page in form.pages
        for section in page.sections
        for block in section.blocks
    )
    for block in blocks:
        if isinstance(block, FormContextFieldBlock):
            _add_form_label(revision, block, labels)
    return labels


def _previous_names(
    provider: PreviousFilingProvider, modelo_id: str, casillas: dict[str, CasillaDefinition]
) -> list[str]:
    keys = provider.source_casilla_ids or (
        (provider.source_casilla_id,) if provider.source_casilla_id is not None and provider.source_casilla_id else ()
    )
    return [
        key if key.isdigit() else casillas[key].label if provider.source_modelo == modelo_id and key in casillas else ""
        for key in keys
    ]


def _previous_label(
    provider: PreviousFilingProvider,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    casillas: dict[str, CasillaDefinition],
) -> str | None:
    names = _previous_names(provider, modelo_id, casillas)
    if not names or not all(names):
        return None
    if isinstance(provider.temporal, FilingYearOffset):
        when = f" · ejercicio {frame.filing_year + provider.temporal.years}"
    elif isinstance(provider.temporal, TargetPeriodOffset):
        when = f" · desplazamiento de {provider.temporal.periods} períodos"
    else:
        return None
    return f"Modelo {provider.source_modelo}{when} · casillas: " + ", ".join(names)


def _row_heading(binding: BindingDefinition, row_bindings: set[str]) -> str | None:
    selector = binding_row_set_selector(binding) if binding.id in row_bindings else None
    return lookup_translation(f"sheets.detalle.headers.{selector.row_field}", locale="es") if selector else None


def _binding_fallback(
    binding: BindingDefinition,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    casillas: dict[str, CasillaDefinition],
    row_bindings: set[str],
) -> str | None:
    if isinstance(binding.provider, AfiliadoContributionProvider):
        target = casillas.get(binding.provider.target_casilla_id)
        if target is not None:
            return target.label
    heading = _row_heading(binding, row_bindings)
    owners = [c.label for c in casillas.values() if c.binding == binding.id]
    if owners:
        return " / ".join(dict.fromkeys(owners))
    if isinstance(binding.provider, PreviousFilingProvider):
        return _previous_label(binding.provider, modelo_id, frame, casillas) or heading
    if isinstance(binding.provider, LedgerRentaIncomeProvider):
        return {
            LedgerIncomeFact.INGRESOS_INTEGROS_SUM: "Ingresos íntegros fiscalmente computables",
            LedgerIncomeFact.CASH_RECEIVED_SUM: "Cobros recibidos",
            LedgerIncomeFact.TAXABLE_BASE_SUM: "Base imponible de los ingresos",
            LedgerIncomeFact.DECLARED_WITHHELD_AMOUNT_SUM: "Retenciones declaradas en las facturas de ingresos",
        }[binding.provider.fact]
    return heading or None


def _binding_labels(
    revision: ModeloRevision,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    casillas: dict[str, CasillaDefinition],
    row_bindings: set[str],
    labels: dict[str, str],
) -> None:
    for binding in revision.bindings:
        declared = lookup_translation(binding_locale_key(modelo_id, binding.id, "label"), locale="es")
        if declared is not None and declared:
            labels[binding.id] = declared
        elif binding.id not in labels:
            label = _binding_fallback(binding, modelo_id, frame, casillas, row_bindings)
            if label is not None:
                labels[binding.id] = label


def _parameter_labels(revision: ModeloRevision, casillas: dict[str, CasillaDefinition], labels: dict[str, str]) -> None:
    consumers: dict[str, list[str]] = {}
    for formula in revision.formulas:
        for key in _leaves(formula.expression):
            consumers.setdefault(key, []).append(casillas[formula.target_casilla_id].label)
    for parameter in revision.parameters:
        owners = consumers.get(parameter.id, [])
        if owners:
            labels[parameter.id] = "Parámetro para: " + " / ".join(dict.fromkeys(owners))


def human_labels[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    revision: ModeloRevision, modelo_id: str, frame: Period | SheetAdministrativeFrame, plan: SheetExportPlan[M]
) -> dict[str, str]:
    """Resolve labels in form, binding and formula authority order.

    Takes ``revision`` as a :class:`ModeloRevision`.
    """
    casillas = {c.id: c for c in revision.casillas}
    labels = _form_labels(revision)
    row_bindings = {column.binding for row_set in plan.row_sets for column in row_set.columns}
    _binding_labels(revision, modelo_id, frame, casillas, row_bindings, labels)
    _parameter_labels(revision, casillas, labels)
    return labels
