"""Load one declaration's editor form, and say what a recalculation changed on it.

The form is a function of four reads: the canonical work review, the revision's
declared form layout, the operator layer recorded on the current calculation
head and the current edit admission. This module reads the first three from the
caller's pinned authority and repositories, takes the admission the caller
already holds, and hands everything to the form builder. It decides nothing the
builder does not.

The loader also reads the two facts the builder cannot: the last day of the
filing window, through the canonical deadline-window resolver and the
business-day shift the calendar applies, and when the AEAT tax data the
current calculation replays was imported, from that snapshot's own record.

Whether a value was entered by the filer is only ever claimed from the recorded
operator layer. A head calculated before operator layers existed, or a head the
calculation catalogue no longer resolves, gives an unknown layer -- never an
empty one -- so the form can say it cannot tell rather than guess.

The change query compares two forms of the same declaration, typically the one
shown before an apply and the one read after it, and lists every field whose
value or origin moved, so the filer sees what their change did to the rest of
the declaration.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core.external_constants import OutputLanguage
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import today_madrid
from ...domain.buckets.event import BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.deadlines.festivos import CalendarCCAA
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .calculation_notes import CALCULATION_NOTES
from .caller_context import caller_context_of
from .edit_models import ModeloEditAdmissionResultV1, ModeloEditAdmittedV1
from .effective_deadline import resolve_effective_filing_deadline
from .work_addressing import law_selected_revision_for_work_target
from .work_form import build_modelo_work_form
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormDeadline,
    ModeloFormExport,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
    ModeloWorkForm,
    address_key,
)
from .work_review import build_modelo_work_review

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ..live.borrador_100 import Borrador100SnapshotRepository

_VERIFIED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    }
)
_FILED_STATES: Final[frozenset[CalculationRevisionState]] = frozenset(
    {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)


class ModeloWorkFormLoadV1(BaseModel):
    """One declaration's form with how far its filing has got."""

    model_config = STRICT_FROZEN_CONFIG

    form: ModeloWorkForm
    verified: bool
    filed: bool


class ModeloFormValueChangeV1(BaseModel):
    """One field whose value or origin differs between two reads of a form."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    box: str | None
    label: ModeloFormText
    before: ModeloFormScalar
    after: ModeloFormScalar
    before_origin: ModeloFormOrigin | None
    after_origin: ModeloFormOrigin | None


def _head(
    calculation_revision_id: str | None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[bool, CalculationRevision | None]:
    """Return whether the head resolved, and the head; no calculation resolves to ``None``."""
    if calculation_revision_id is None:
        return True, None
    head = calculation_repository.load(operation=operation).get(calculation_revision_id)
    return head is not None, head


def modelo_form_snapshot(
    operation: PinnedAuthorityOperation, modelo: ModeloCode, filing_year: int, period: Period, revision_id: str
) -> RegistrySnapshot:
    """The snapshot a form reads its revision through, at the grade that revision declares.

    The law selects the revision for the filing context; ``revision_id``, the
    one the declaration was worked under, is only asserted against that
    selection, never used to choose it. Asking every revision for filing grade
    would refuse an applicability-only one the filer can still open and
    inspect, so the form asks for what the revision actually claims, as the
    work review does.
    """
    selected = law_selected_revision_for_work_target(
        modelo=str(modelo), filing_year=filing_year, period=period, stored_revision_id=revision_id, operation=operation
    )
    grade = operation.revision(str(modelo), selected).effective_authority_grade
    return operation.snapshot(str(modelo), filing_year=filing_year, period=period.registry_token, grade=grade)


def modelo_form_deadline(
    operation: PinnedAuthorityOperation,
    modelo: ModeloCode,
    period: Period,
    *,
    holiday_territory: CalendarCCAA | None,
    reference_on: date,
) -> ModeloFormDeadline | None:
    """The last day of the declaration's voluntary filing window, or ``None`` when none is declared.

    The window comes from the canonical resolver the calendar and the
    extemporaneity notice use; it stores the nominal statutory date, which the
    business-day shift moves past weekends and holidays at read time. Without
    the filer's territory only national holidays are checked, and a year with
    no published holiday calendar moves past weekends only; the coverage says
    which, so neither is shown as a final date.

    Raises:
        RegistryError: The registry could not be read, so the deadline is
            unknown rather than absent.
        DeadlineValidationError: More than one window matches the declaration.
    """
    deadline = resolve_effective_filing_deadline(
        str(modelo), period.filing_year, period, holiday_territory=holiday_territory, operation=operation
    )
    if deadline is None:
        return None
    return ModeloFormDeadline(
        closes_on=deadline.closes_on,
        nominal_closes_on=deadline.nominal_closes_on,
        holiday_coverage=deadline.holiday_coverage,
        reference_on=reference_on,
        days_remaining=deadline.days_remaining_on(reference_on),
        days_overdue=deadline.days_overdue_on(reference_on),
    )


def _aeat_data_imported_at(
    snapshot_id: str | None, borrador_snapshots: Borrador100SnapshotRepository | None
) -> datetime | None:
    """When the AEAT tax data the calculation replays was imported, if its record can be read here."""
    if snapshot_id is None or borrador_snapshots is None or not borrador_snapshots.exists(snapshot_id):
        return None
    return borrador_snapshots.load(snapshot_id).captured_at


def load_modelo_work_form(
    bucket_id: BucketId,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    *,
    operation: PinnedAuthorityOperation,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    admission: ModeloEditAdmissionResultV1 | None,
    language: OutputLanguage,
    borrador_snapshots: Borrador100SnapshotRepository | None = None,
    holiday_territory: CalendarCCAA | None = None,
    reference_on: date | None = None,
    bucket_events: BucketEventHistoryRepositoryProtocol | None = None,
) -> ModeloWorkFormLoadV1:
    """Read one declaration's review, layout and operator layer and build its form.

    ``admission`` is the edit admission the caller holds for this declaration,
    or ``None`` when none was sought; a refused admission, or one for another
    work unit, offers nothing for editing.

    ``borrador_snapshots`` is the profile's AEAT draft store, read only for
    when the replayed draft was imported; without it the form still says the
    draft feeds the declaration, with no import time. ``holiday_territory`` is
    the filer's autonomous community for the deadline's holiday shift, and
    ``reference_on`` the day the days left are counted from, today in Madrid by
    default. ``bucket_events`` is the profile's event history, read only for
    the latest file exported for this declaration; without it the form states
    no export.
    """
    review = build_modelo_work_review(
        bucket_id,
        modelo,
        filing_year,
        period,
        operation=operation,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
    )
    snapshot = modelo_form_snapshot(operation, modelo, filing_year, period, review.registry_revision_id)
    layout = operation.form_layout(str(modelo), review.registry_revision_id)
    resolved, head = _head(review.calculation_revision_id, calculation_repository, operation=operation)
    context = caller_context_of(head)
    layer = context.operator_layer if resolved else None
    surface = (
        admission.baseline.permitted_surface
        if isinstance(admission, ModeloEditAdmittedV1)
        and str(admission.baseline.work_unit_id) == str(review.work_unit_id)
        else None
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout,
        revision=head,
        permitted_surface=surface,
        entered_casilla_ids=None if layer is None else frozenset(layer.casilla_ids()),
        overridden_binding_ids=None if layer is None else frozenset(layer.binding_overrides),
        language=language,
        deadline=modelo_form_deadline(
            operation,
            modelo,
            period,
            holiday_territory=holiday_territory,
            reference_on=reference_on if reference_on is not None else today_madrid(),
        ),
        aeat_data_imported_at=_aeat_data_imported_at(context.borrador_snapshot_id, borrador_snapshots),
        calculation_diagnostics=CALCULATION_NOTES.diagnostics_for(
            str(review.work_unit_id), review.calculation_revision_id
        ),
    )
    form = form.model_copy(
        update={
            "last_export": _last_export(
                bucket_events, bucket_id, str(review.work_unit_id), review.calculation_revision_id
            )
        }
    )
    state = review.lifecycle_state
    return ModeloWorkFormLoadV1(form=form, verified=state in _VERIFIED_STATES, filed=state in _FILED_STATES)


def _last_export(
    bucket_events: BucketEventHistoryRepositoryProtocol | None,
    bucket_id: BucketId,
    work_unit_id: str,
    current_revision_id: str | None,
) -> ModeloFormExport | None:
    """The latest export of this declaration, from its durable event, whatever calculation it was made from."""
    if bucket_events is None:
        return None
    exported = [
        event
        for event in bucket_events.load().for_bucket(str(bucket_id), event_types=(BucketEventType.MODELO_EXPORTED,))
        if event.payload.get("work_unit_id") == work_unit_id and event.payload.get("calculation_revision_id")
    ]
    if not exported:
        return None
    latest = exported[-1]
    revision_id = str(latest.payload["calculation_revision_id"])
    return ModeloFormExport(
        exported_at=latest.occurred_at, calculation_revision_id=revision_id, current=revision_id == current_revision_id
    )


def modelo_work_form_changes(before: ModeloWorkForm, after: ModeloWorkForm) -> tuple[ModeloFormValueChangeV1, ...]:
    """List every field whose value or origin differs between two forms of one declaration.

    Fields come in the later form's reading order, then any the later form no
    longer shows.
    """
    earlier = {address_key(field.address): field for field in before.fields()}
    later = {address_key(field.address): field for field in after.fields()}
    changes: list[ModeloFormValueChangeV1] = []
    for key, field in later.items():
        previous = earlier.get(key)
        if _same_form_value(previous, field):
            continue
        changes.append(
            ModeloFormValueChangeV1(
                address=field.address,
                box=field.box,
                label=field.label,
                before=None if previous is None else previous.value,
                after=field.value,
                before_origin=None if previous is None else previous.origin,
                after_origin=field.origin,
            )
        )
    changes.extend(
        ModeloFormValueChangeV1(
            address=field.address,
            box=field.box,
            label=field.label,
            before=field.value,
            after=None,
            before_origin=field.origin,
            after_origin=None,
        )
        for key, field in earlier.items()
        if key not in later
    )
    return tuple(changes)


def _same_form_value(previous: ModeloFormField | None, current: ModeloFormField) -> bool:
    return previous is not None and previous.value == current.value and previous.origin is current.origin


__all__ = [
    "ModeloFormValueChangeV1",
    "ModeloWorkFormLoadV1",
    "load_modelo_work_form",
    "modelo_form_deadline",
    "modelo_form_snapshot",
    "modelo_work_form_changes",
]
