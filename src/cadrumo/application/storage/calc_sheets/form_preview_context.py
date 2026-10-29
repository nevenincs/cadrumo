"""Fictional workbook form context from the preview frame and producer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core.filing_producer_key import FilingProducerKey
from ....core.period import Period
from ....domain.calculations.registry.export_semantics import ExportDraftAttribute
from ....domain.calculations.registry.form_context import resolve_form_context_field
from ....domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ...modelo.work_form_models import ModeloFormScalar
from .errors import CalcSheetsEngineError
from .template_source import WorkbookTemplateSource


def preview_context(
    source: WorkbookTemplateSource, illustrative_values: dict[FilingProducerKey, object], block: FormContextFieldBlock
) -> ModeloFormScalar:
    """Resolve only supported illustrative scalar values."""
    field = resolve_form_context_field(source.revision, block)
    frame = source.preview_frame
    if field.draft_attribute is ExportDraftAttribute.FILING_YEAR:
        return frame.filing_year
    if field.draft_attribute is ExportDraftAttribute.PERIOD_CODE:
        return frame.code
    if isinstance(frame, Period) and frame.has_date_span():
        if field.draft_attribute is ExportDraftAttribute.PERIOD_START_DATE:
            return frame.start_date
        if field.draft_attribute is ExportDraftAttribute.PERIOD_END_DATE:
            return frame.end_date
    value = (
        illustrative_values.get(field.producer_key) if (field.producer_key is not None and field.producer_key) else None
    )
    return _scalar(value)


def _scalar(value: object) -> ModeloFormScalar:
    if value is None or isinstance(value, (str, bool, int, Decimal, date)):
        return value
    raise CalcSheetsEngineError("illustrative form context is not a supported scalar")
