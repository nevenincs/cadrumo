"""Read-only filing context selected by a declared form, never a profile dump.

:class:`CalculationRevision` holds the saved calculation and its evidence.
:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export_semantics import ExportDraftAttribute
from ...domain.calculations.registry.form_context import FORM_CONTEXT_DRAFT_ATTRIBUTES, resolve_form_context_field
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock
from ...domain.modelos.calculation_revision import CalculationRevision
from ..filing.export_producer import filing_producer_values
from ..filing.producer_snapshot import FilingProducerSnapshot
from .registry_input_refusals import registry_integrity_verdict, request_verdict
from .work_form_field_vocabulary import ModeloFormScalar
from .work_form_projection_records import saved_projection_context_value


def form_context_value(
    snapshot: RegistrySnapshot,
    block: FormContextFieldBlock,
    *,
    producer_snapshot: FilingProducerSnapshot | None = None,
    producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None = None,
    revision: CalculationRevision | None = None,
) -> ModeloFormScalar:
    """Project only the addressed scalar; absent producer facts remain unknown.

    No profile is opened here. The caller supplies admitted producer values or
    a filing snapshot explicitly. A supplied snapshot takes precedence and
    facts for a different modelo are refused even when the requested field
    itself is a year or period. Missing keys never acquire default values.

    The ``revision`` parameter uses :class:`CalculationRevision`, which holds the saved calculation and its evidence.
    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    if producer_snapshot is not None and str(producer_snapshot.modelo) != snapshot.modelo.id:
        raise RegistryValidationError(
            "form context producer belongs to another modelo",
            precondition_verdict=request_verdict("form_context_producer_modelo"),
        )
    field = resolve_form_context_field(snapshot.revision, block)
    if field.projection_ref is not None:
        return saved_projection_context_value(snapshot=snapshot, revision=revision, block=block)
    if field.binding is not None:
        raise RegistryValidationError(
            "binding context requires the saved binding or workbook projection",
            precondition_verdict=request_verdict("form_context_binding_source"),
        )
    if field.draft_attribute in FORM_CONTEXT_DRAFT_ATTRIBUTES:
        return _draft_context_value(snapshot, field.draft_attribute)
    return _producer_context_value(producer_snapshot, field.producer_key, producer_values)


def _draft_context_value(snapshot: RegistrySnapshot, attribute: ExportDraftAttribute | None) -> ModeloFormScalar:
    if attribute is ExportDraftAttribute.FILING_YEAR:
        return snapshot.filing_year
    if attribute is ExportDraftAttribute.PERIOD_CODE:
        return snapshot.period
    if attribute in (ExportDraftAttribute.PERIOD_START_DATE, ExportDraftAttribute.PERIOD_END_DATE):
        # These exact draft fields use draft.period in the filing renderer.
        # A fiscal-start header producer is a different fact and never inferred here.
        period = snapshot.filing_period
        if period is None or not period.has_date_span():
            return None
        return period.start_date if attribute is ExportDraftAttribute.PERIOD_START_DATE else period.end_date
    raise RegistryValidationError(
        "unsupported draft context value",
        precondition_verdict=registry_integrity_verdict("form_context_draft_attribute"),
    )


def _producer_context_value(
    producer_snapshot: FilingProducerSnapshot | None,
    producer_key: FilingProducerKey | None,
    producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None,
) -> ModeloFormScalar:
    if producer_key is None:
        return None
    values = filing_producer_values(producer_snapshot) if producer_snapshot is not None else producer_values
    value = None if values is None else values.get(producer_key)
    if value is None or isinstance(value, (str, bool, int, Decimal, date)):
        return value
    raise RegistryValidationError(
        "form context producer value is not a supported scalar",
        precondition_verdict=registry_integrity_verdict("form_context_producer_value"),
    )
