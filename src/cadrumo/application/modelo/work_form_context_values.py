"""Read-only filing context selected by a declared form, never a profile dump."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export_semantics import ExportDraftAttribute
from ...domain.calculations.registry.form_context import resolve_form_context_field
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ...domain.modelos.calculation_revision import CalculationRevision
from ..filing.export_producer import filing_producer_values
from ..filing.producer_snapshot import FilingProducerSnapshot
from .work_form_models import ModeloFormScalar
from .work_form_projection_records import saved_projection_context_value


def form_context_value(
    snapshot: RegistrySnapshot,
    block: FormContextFieldBlock,
    *,
    producer_snapshot: FilingProducerSnapshot | None = None,
    revision: CalculationRevision | None = None,
) -> ModeloFormScalar:
    """Project only the addressed scalar; absent producer facts remain unknown.

    No profile is opened here. The caller supplies an admitted filing snapshot
    explicitly, and facts for a different modelo are refused even when the
    requested field itself is a year or period.
    """
    if producer_snapshot is not None and str(producer_snapshot.modelo) != str(snapshot.modelo.id):
        raise RegistryValidationError("form context producer belongs to another modelo")
    field = resolve_form_context_field(snapshot.revision, block)
    if field.projection_ref is not None:
        return saved_projection_context_value(snapshot=snapshot, revision=revision, block=block)
    if field.binding is not None:
        raise RegistryValidationError("binding context requires the saved binding or workbook projection")
    if field.draft_attribute is ExportDraftAttribute.FILING_YEAR:
        return snapshot.filing_year
    if field.draft_attribute is ExportDraftAttribute.PERIOD_CODE:
        return str(snapshot.period)
    if field.draft_attribute in (ExportDraftAttribute.PERIOD_START_DATE, ExportDraftAttribute.PERIOD_END_DATE):
        # These exact draft fields use draft.period in the filing renderer.
        # A fiscal-start header producer is a different fact and never inferred here.
        period = snapshot.filing_period
        if period is None or not period.has_date_span():
            return None
        return period.start_date if field.draft_attribute is ExportDraftAttribute.PERIOD_START_DATE else period.end_date
    if producer_snapshot is None:
        return None
    value = filing_producer_values(producer_snapshot).get(field.producer_key) if field.producer_key else None
    if value is None or isinstance(value, (str, bool, int, Decimal, date)):
        return value
    raise RegistryValidationError("form context producer value is not a supported scalar")
