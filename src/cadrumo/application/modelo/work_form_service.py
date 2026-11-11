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

import contextlib
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.aggregation import BindingSourceKind
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.filing_producer_key import FilingProducerKey
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import today_madrid
from ...domain.buckets.event import BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.form_context import resolve_form_context_field
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_wallet_carry_targets import revision_offers_iva_wallet
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormLayoutDefinition
from ...domain.deadlines.effective_close import resolve_effective_filing_deadline
from ...domain.iva.refund_eligibility import RedemeEnrolmentState, redeme_enrolment_state
from ...domain.modelos.calculation_revision import (
    FILED_REVISION_STATES,
    SEALED_REVISION_STATES,
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.user_profile.errors import ProfileSchemaValidationError
from ..actividad_asset.ports import ActivityAssetHistoryRepository
from ..aggregation.renta_imputation import revision_reads_imputation_criterion
from ..filing.export_producer import (
    M303_LEXICAL_PRODUCER_KEYS,
    M303FilingLexicals,
    M303ProfileLexicals,
    m303_context_producer_values,
    m303_evidence_lexicals,
    m303_filing_lexicals,
)
from ..live.borrador_100_import import borrador_pdf_extraction_profile
from ..user_profile.projections import declared_redeme_enrolment, profile_path_values_for_bucket
from .calculation_note_gate import (
    NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    calculation_filed_before_grade_cap,
    calculation_screen_outdated,
)
from .calculation_notes import CALCULATION_NOTES, read_element_names
from .caller_context import caller_context_of
from .credit_resolution import load_credit_resolutions
from .credit_resolution_repository import CreditResolutionReader
from .edit_models import ModeloEditAdmissionResultV1, ModeloEditAdmittedV1
from .export_accounts import resolve_m303_filing_facts_from_arrivals
from .export_ports import M303ArrivalPorts
from .profile_binding import resolve_profile_sourced_bindings
from .profile_export_binding import resolve_m303_profile_lexicals, resolve_profile_identity_producer_values
from .projection_declaration import modelo_projection_available
from .taxation_comparison import revision_compares_taxation
from .work_addressing import law_selected_revision_for_work_target
from .work_form import build_modelo_work_form
from .work_form_declaration_facts import ModeloFormDeadline, ModeloFormExport
from .work_form_field_vocabulary import (
    ModeloFormAddressV1,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloFormText,
    address_key,
)
from .work_form_models import (
    ModeloFormField,
    ModeloWorkForm,
)
from .work_review import build_modelo_work_review

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import RegistrySnapshot
    from ..live.borrador_100 import Borrador100SnapshotRepository


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
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
) -> tuple[bool, CalculationRevision | None]:
    """Return whether the head resolved, and the head; no calculation resolves to ``None``."""
    if calculation_revision_id is None:
        return True, None
    catalogue = (
        calculation_catalogue if calculation_catalogue is not None else calculation_repository.load(operation=operation)
    )
    head = catalogue.get(calculation_revision_id)
    return head is not None, head


def modelo_form_snapshot(
    operation: PinnedAuthorityOperation,
    modelo: ModeloCode,
    filing_year: int,
    period: Period,
    revision_id: str | None = None,
) -> RegistrySnapshot:
    """The snapshot a declaration is read through, at the grade its revision declares.

    The law selects the revision for the filing context; ``revision_id``, the
    one the declaration was worked under, is only asserted against that
    selection, never used to choose it, and a reader with no stored revision
    reads the law's selection as it is. Asking every revision for filing grade
    would refuse an applicability-only one the filer can still open and
    inspect, so every reader of a declaration asks for what the revision
    actually claims, as the work review does; the filing gates ask for filing
    grade where they apply.
    """
    law_selected_revision_for_work_target(
        modelo=str(modelo), filing_year=filing_year, period=period, stored_revision_id=revision_id, operation=operation
    )
    grade = operation.reachable_authority_grade(str(modelo), filing_year=filing_year, period=period.registry_token)
    return operation.snapshot(str(modelo), filing_year=filing_year, period=period.registry_token, grade=grade)


def modelo_form_deadline(
    operation: PinnedAuthorityOperation,
    modelo: ModeloCode,
    period: Period,
    *,
    reference_on: date,
) -> ModeloFormDeadline | None:
    """The last day of the declaration's voluntary filing window, or ``None`` when none is declared.

    The window comes from the canonical resolver the calendar and the
    extemporaneity notice use; it stores the nominal statutory date, which the
    business-day shift moves past weekends and national inhábiles at read
    time. A holiday calendar that cannot be read leaves the nominal date
    standing and the coverage says so, so it is not shown as a final date.

    Raises:
        RegistryError: The registry could not be read, so the deadline is
            unknown rather than absent.
        DeadlineValidationError: More than one window matches the declaration.
    """
    deadline = resolve_effective_filing_deadline(str(modelo), period.filing_year, period, operation=operation)
    if deadline is None:
        return None
    posture = deadline.posture_on(reference_on)
    days_remaining = posture.days_remaining
    days_overdue = posture.days_overdue
    if days_remaining is None and days_overdue is None:
        # The window's close is unknown and its nominal close has passed, so
        # neither posture can be stated.
        return None
    return ModeloFormDeadline(
        closes_on=deadline.closes_on,
        nominal_closes_on=deadline.nominal_closes_on,
        holiday_coverage=deadline.holiday_coverage,
        reference_on=reference_on,
        days_remaining=days_remaining,
        days_overdue=days_overdue,
    )


def _known_profile_truths(
    snapshot: RegistrySnapshot, bucket_id: BucketId, *, operation: PinnedAuthorityOperation
) -> Mapping[BindingId, bool]:
    """The yes-or-no facts the filer's stored profile states, which decide the guards a calculation branches on.

    Only a revision with an input the filer types has a refusal to predict, so
    any other revision reads nothing. A profile that cannot be read states no
    fact: the form then claims no refusal that depends on one.
    """
    if not any(binding.source is BindingSourceKind.MANUAL_INPUT for binding in snapshot.revision.bindings):
        return dict[BindingId, bool]()
    try:
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=str(bucket_id), operation=operation)
    except RegistryValidationError:
        return dict[BindingId, bool]()
    return dict(resolution.boolean_binding_values)


def _redeme_enrolment(bucket_id: BucketId) -> RedemeEnrolmentState:
    """The filer's stated inscription in the Registro de devolución mensual.

    A profile that cannot be read, or one that has not answered, stays
    unstated: the form then offers only the disposition that is lawful whatever
    the answer, and says which fact the refund needs.
    """
    return redeme_enrolment_state(declared_redeme_enrolment(profile_path_values_for_bucket(str(bucket_id))))


def _aeat_data_imported_at(
    snapshot_id: str | None, borrador_snapshots: Borrador100SnapshotRepository | None
) -> datetime | None:
    """When the AEAT tax data the calculation replays was imported, if its record can be read here."""
    if snapshot_id is None or borrador_snapshots is None or not borrador_snapshots.exists(snapshot_id):
        return None
    return borrador_snapshots.load(snapshot_id).captured_at


def _current_profile_context_allowed(
    layout: FormLayoutDefinition | None,
    snapshot: RegistrySnapshot,
    lifecycle_state: CalculationRevisionState | None,
) -> bool:
    """Current profile facts cannot attest a historical or unusable form."""
    return (
        layout is not None
        and layout.revision_id == snapshot.revision.id
        and lifecycle_state not in FILED_REVISION_STATES
        and lifecycle_state is not CalculationRevisionState.DESCARTADO
    )


def _profile_context_values(
    layout: FormLayoutDefinition | None,
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
    lifecycle_state: CalculationRevisionState | None,
    *,
    bucket_id: BucketId,
    operation: PinnedAuthorityOperation,
    m303_arrivals: M303ArrivalPorts | None,
) -> Mapping[FilingProducerKey, ModeloFormScalar]:
    """Resolve the producer context a layout declares, as the export resolves it.

    Current identity and enrolment facts come from the profile and only for an
    open form; the filing answers saved on the revision come from the revision,
    whatever its state. Nothing else is read.
    """
    if layout is None or layout.revision_id != snapshot.revision.id:
        return dict[FilingProducerKey, ModeloFormScalar]()
    producers = {
        producer
        for block in _context_field_blocks(layout)
        if (producer := resolve_form_context_field(snapshot.revision, block).producer_key) is not None
    }
    if not producers:
        return dict[FilingProducerKey, ModeloFormScalar]()
    current = _current_profile_context_allowed(layout, snapshot, lifecycle_state)
    values: dict[FilingProducerKey, ModeloFormScalar] = {}
    if current:
        values.update(_profile_identity_values(bucket_id=bucket_id, operation=operation))
    if producers & M303_LEXICAL_PRODUCER_KEYS:
        values.update(
            _m303_context_values(
                snapshot,
                revision,
                bucket_id=bucket_id,
                operation=operation,
                read_profile=current,
                arrivals=m303_arrivals,
            )
        )
    return values


def _profile_identity_values(
    *, bucket_id: BucketId, operation: PinnedAuthorityOperation
) -> Mapping[FilingProducerKey, ModeloFormScalar]:
    try:
        return resolve_profile_identity_producer_values(bucket_id=str(bucket_id), operation=operation)
    except ProfileSchemaValidationError:
        # A stored name past a producer's bound cannot be shaped into header
        # context. The form still opens and the header states no identity; the
        # export path is what refuses it and names the profile field to shorten.
        return dict[FilingProducerKey, ModeloFormScalar]()


def _m303_context_values(
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
    *,
    bucket_id: BucketId,
    operation: PinnedAuthorityOperation,
    read_profile: bool,
    arrivals: M303ArrivalPorts | None,
) -> Mapping[FilingProducerKey, ModeloFormScalar]:
    """The Modelo 303 identification answers, through the export's own lexical projection.

    The saved filing evidence supplies the filer's answers for this filing and
    the profile the enrolments. With the arrival repositories the ledger and
    register facts are folded in by the function the export folds them with;
    without them, or when that fold refuses, those answers stay unknown and
    export is what refuses and says why.
    """
    profile = (
        resolve_m303_profile_lexicals(bucket_id=str(bucket_id), operation=operation, period=snapshot.filing_period)
        if read_profile
        else M303ProfileLexicals()
    )
    evidence = None if revision is None else revision.filing_instance_evidence
    filing = M303FilingLexicals() if evidence is None else m303_evidence_lexicals(evidence.m303)
    period = snapshot.filing_period
    if evidence is not None and arrivals is not None and period is not None:
        with contextlib.suppress(CadrumoError):
            filing = m303_filing_lexicals(
                resolve_m303_filing_facts_from_arrivals(
                    bucket_id=str(bucket_id), period=period, evidence=evidence, arrivals=arrivals, operation=operation
                )
            )
    values: dict[FilingProducerKey, ModeloFormScalar] = {}
    for key, value in m303_context_producer_values(profile, filing).items():
        if value is not None and not isinstance(value, str):
            raise RegistryValidationError("form context producer value is not a supported scalar")
        values[key] = value
    return values


def _needed_profile_bindings(
    layout: FormLayoutDefinition, snapshot: RegistrySnapshot, revision: CalculationRevision | None
) -> set[BindingId]:
    """Profile-sourced bindings the layout's context fields read that the revision has no saved answer for."""
    profiles = {binding.id for binding in snapshot.revision.bindings if binding.source is BindingSourceKind.PROFILE}
    needed: set[BindingId] = set()
    for block in _context_field_blocks(layout):
        binding = resolve_form_context_field(snapshot.revision, block).binding
        if binding is None or binding not in profiles:
            continue
        if revision is None or binding not in revision.binding_overrides:
            needed.add(binding)
    return needed


def _context_field_blocks(layout: FormLayoutDefinition) -> Iterator[FormContextFieldBlock]:
    """The layout's context field blocks in page, section and block order."""
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, FormContextFieldBlock):
                    yield block


def _profile_binding_context_values(
    layout: FormLayoutDefinition | None,
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
    lifecycle_state: CalculationRevisionState | None,
    *,
    bucket_id: BucketId,
    operation: PinnedAuthorityOperation,
) -> Mapping[BindingId, ModeloFormScalar]:
    """Resolve only declared profile binding context that has no saved answer."""
    if layout is None or not _current_profile_context_allowed(layout, snapshot, lifecycle_state):
        return dict[BindingId, ModeloFormScalar]()
    needed = _needed_profile_bindings(layout, snapshot, revision)
    if not needed:
        return dict[BindingId, ModeloFormScalar]()
    try:
        resolution = resolve_profile_sourced_bindings(snapshot, bucket_id=str(bucket_id), operation=operation)
    except RegistryValidationError:
        return dict[BindingId, ModeloFormScalar]()
    values: dict[BindingId, ModeloFormScalar] = {
        **resolution.binding_values,
        **resolution.enum_binding_values,
        **resolution.date_binding_values,
        **resolution.boolean_binding_values,
    }
    return {binding_id: value for binding_id, value in values.items() if binding_id in needed}


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
    calculation_catalogue: CalculationRevisionCatalogue | None = None,
    admission: ModeloEditAdmissionResultV1 | None,
    language: OutputLanguage,
    borrador_snapshots: Borrador100SnapshotRepository | None = None,
    reference_on: date | None = None,
    bucket_events: BucketEventHistoryRepositoryProtocol | None = None,
    activity_assets: ActivityAssetHistoryRepository | None = None,
    credit_resolutions: CreditResolutionReader | None = None,
    m303_arrivals: M303ArrivalPorts | None = None,
) -> ModeloWorkFormLoadV1:
    """Read one declaration's review, layout and operator layer and build its form.

    ``admission`` is the edit admission the caller holds for this declaration,
    or ``None`` when none was sought; a refused admission, or one for another
    work unit, offers nothing for editing.

    ``calculation_catalogue`` may carry the caller's freshly validated read
    from this same synchronous form assembly. The review and operator layer
    then use that one read; standalone callers retain their repository reads.

    ``borrador_snapshots`` is the profile's AEAT draft store, read only for
    when the replayed draft was imported; without it the form still says the
    draft feeds the declaration, with no import time. ``reference_on`` is the
    day the days left are counted from, today in Madrid by default.
    ``bucket_events`` is the profile's event history, read only for the latest
    file exported for this declaration; without it the form states no export.
    ``credit_resolutions`` is the profile's store of accepted source
    disagreements; without it none is honoured, so every disagreement holds
    filing, and one that cannot be read is held the same way.

    ``m303_arrivals`` are the ledger and register repositories a Modelo 303 period
    facts are folded from, exactly as its export folds them. Without them the
    facts that come from those arrivals stay unknown on the form.
    """
    resolutions = (
        NO_SOURCE_DISAGREEMENT_RESOLUTIONS
        if credit_resolutions is None
        else load_credit_resolutions(
            credit_resolutions,
            modelo=str(modelo),
            filing_year=filing_year,
            period=period.registry_token,
        ).resolutions
    )
    review = build_modelo_work_review(
        bucket_id,
        modelo,
        filing_year,
        period,
        operation=operation,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        calculation_catalogue=calculation_catalogue,
        resolutions=resolutions,
    )
    snapshot = modelo_form_snapshot(operation, modelo, filing_year, period, review.registry_revision_id)
    layout = operation.form_layout(str(modelo), review.registry_revision_id)
    resolved, head = _head(
        review.calculation_revision_id,
        calculation_repository,
        operation=operation,
        calculation_catalogue=calculation_catalogue,
    )
    context = caller_context_of(head)
    layer = context.operator_layer if resolved else None
    surface = (
        admission.baseline.permitted_surface
        if isinstance(admission, ModeloEditAdmittedV1) and admission.baseline.work_unit_id == review.work_unit_id
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
            reference_on=reference_on if reference_on is not None else today_madrid(),
        ),
        aeat_data_imported_at=_aeat_data_imported_at(context.borrador_snapshot_id, borrador_snapshots),
        calculation_diagnostics=CALCULATION_NOTES.diagnostics_for(review.work_unit_id, review.calculation_revision_id),
        element_names=read_element_names(activity_assets),
        known_truths=_known_profile_truths(snapshot, bucket_id, operation=operation),
        redeme=_redeme_enrolment(bucket_id),
        producer_values=_profile_context_values(
            layout,
            snapshot,
            head,
            review.lifecycle_state,
            bucket_id=bucket_id,
            operation=operation,
            m303_arrivals=m303_arrivals,
        ),
        profile_binding_values=_profile_binding_context_values(
            layout, snapshot, head, review.lifecycle_state, bucket_id=bucket_id, operation=operation
        ),
        resolutions=resolutions,
        calculation_screen_outdated=head is not None
        and calculation_screen_outdated(
            head, modelo=str(modelo), filing_year=filing_year, period=period, operation=operation
        ),
        calculation_filed_before_grade_cap=None
        if head is None
        else calculation_filed_before_grade_cap(
            head, modelo=str(modelo), filing_year=filing_year, period=period, operation=operation
        ),
    )
    form = form.model_copy(
        update={
            "last_export": _last_export(bucket_events, bucket_id, review.work_unit_id, review.calculation_revision_id),
            "projectable": modelo_projection_available(
                modelo=str(modelo),
                period=period,
                filing_year=filing_year,
                registry_revision_id=review.registry_revision_id,
                operation=operation,
            ),
            "asks_imputation_election": revision_reads_imputation_criterion(snapshot.revision),
            "compares_taxation": revision_compares_taxation(snapshot),
            "compares_borrador": borrador_pdf_extraction_profile(snapshot) is not None,
            "offers_iva_wallet": revision_offers_iva_wallet(modelo_id=snapshot.modelo.id, revision=snapshot.revision),
        }
    )
    state = review.lifecycle_state
    return ModeloWorkFormLoadV1(
        form=form, verified=state in SEALED_REVISION_STATES, filed=state in FILED_REVISION_STATES
    )


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
        for event in bucket_events.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))
        if event.payload.get("work_unit_id") == work_unit_id and bool(event.payload.get("calculation_revision_id"))
    ]
    if not exported:
        return None
    latest = exported[-1]
    revision_id = latest.payload["calculation_revision_id"]
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
