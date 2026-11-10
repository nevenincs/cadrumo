"""A declaration's editor form says what the filer entered only from the recorded operator layer.

Driven over real encrypted storage through the production calculation, edit
and verification executors, then read back through the form loading service
with the pinned authority's published layout. A value the filer typed reads as
entered and stays so after a recalculation; a declaration nobody has
calculated knows it holds no entries; the admission the caller holds decides
what is offered for editing, and one for another declaration offers nothing.

The form asks the filer for exactly the boxes the real verification finds
missing, never a box it does not, and states the result's direction and the
last day to file. Once the declaration is recorded as filed it offers nothing
for editing, whatever the admission says, and says why; and a value an
imported AEAT draft supplied reads as AEAT data.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from cadrumo.entrypoints.tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ...adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ...application.modelo.calculation_note_gate import ModeloCalculationBlockedError, blocking_calculation_issues
from ...application.modelo.calculation_notes import CALCULATION_NOTES
from ...application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.operation_definitions import ModeloWorkVerifyExecutor
from ...application.modelo.operation_shared import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    resolve_active_workflow_profile,
)
from ...application.modelo.source_policy import SourceFamily
from ...application.modelo.work_form import build_modelo_work_form
from ...application.modelo.work_form_declaration_facts import ModeloFormEditClosure, ModeloFormResultDirection
from ...application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    address_key,
)
from ...application.modelo.work_form_issue_lines import form_issue_lines
from ...application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloWorkForm,
)
from ...application.modelo.work_form_service import ModeloWorkFormLoadV1, load_modelo_work_form, modelo_form_snapshot
from ...application.modelo.work_review import ModeloWorkReview, build_modelo_work_review
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...core.casilla_id import validated_casilla_id
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.calculation_revision_sources import CalculationNoteSentence
from ...domain.modelos.verification_report import ModeloVerificationFindingKind
from ..adapter_composition_work_ports import build_verification_repository_bundle
from .executor_context_stand_ins import RecordedEvents, RecordedOperands, UninterruptedCancellation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")
_C02 = validated_casilla_id("02")
_C13 = validated_casilla_id("13")
_REFERENCE_DAY = date(2026, 4, 2)
_FILED_AT = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
_IMPORTED_AT = datetime(2026, 4, 2, 8, 30, tzinfo=UTC)
_SNAPSHOT_ID = "e" * 64
_EDITABLE = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)


def _load(
    work: SeededOperatorWork, admission: ModeloEditAdmissionResultV1 | None, *, reference_on: date | None = None
) -> ModeloWorkFormLoadV1:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
        admission=admission,
        language=OutputLanguage.ES,
        reference_on=reference_on,
    )


def _field(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(field for field in form.fields() if address_key(field.address) == ("casilla", casilla_id))


@dataclass(frozen=True, slots=True)
class _Context:
    """The slice of the supervisor context the verify executor reads."""

    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: RecordedEvents
    cancellation: UninterruptedCancellation = field(default_factory=UninterruptedCancellation)
    operands: RecordedOperands = field(default_factory=RecordedOperands)


def _verify(work: SeededOperatorWork) -> ModeloWorkVerifyPublicResultV2:
    """Verify the current head through the production verify executor, as its operation would."""
    payload = ModeloWorkVerifyRequest(
        calculation_revision_id=work.require_head().calculation_revision_id, actor="operator:test"
    )
    request = OperationRequest(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID, subject_ref=work.work_unit_id, payload=payload
    )
    context = _Context(
        identity=OperationIdentity(
            operation_id=content_hash_hex({"verify": payload.model_dump(mode="json")}),
            definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
            subject_ref=work.work_unit_id,
        ),
        authority_operation=work.operation,
        events=RecordedEvents(),
    )
    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=build_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    result_ref = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    assert result_ref is not None
    (result,) = context.operands.results
    assert isinstance(result, ModeloWorkVerifyPublicResultV2)
    assert result.calculation_revision_id == payload.calculation_revision_id
    return result


def _rebuilt(work: SeededOperatorWork, head: CalculationRevision, review: ModeloWorkReview) -> ModeloWorkForm:
    """Build the form over ``head`` and ``review`` as the loader would, with an admission the caller holds."""
    admission = work.admit()
    assert isinstance(admission, ModeloEditAdmittedV1)
    unit = work.work_unit
    snapshot = modelo_form_snapshot(
        work.operation, unit.modelo, unit.filing_year, unit.period, review.registry_revision_id
    )
    layer = head.operator_layer
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=work.operation.form_layout(str(unit.modelo), review.registry_revision_id),
        revision=head,
        permitted_surface=admission.baseline.permitted_surface,
        entered_casilla_ids=None if layer is None else frozenset(layer.casilla_ids()),
        overridden_binding_ids=None if layer is None else frozenset(layer.binding_overrides),
        language=OutputLanguage.ES,
        aeat_data_imported_at=_IMPORTED_AT,
    )


def _review(work: SeededOperatorWork) -> ModeloWorkReview:
    unit = work.work_unit
    return build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
    )


def test_a_typed_value_reads_as_entered_and_survives_a_recalculation(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        fresh = _load(work, work.admit())
        applied = work.apply(
            scalar=(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=_C06),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value="100",
                ),
            )
        )
        assert applied.refusal is None
        edited = _load(work, work.admit())
        work.recalculate()
        recalculated = _load(work, None)

    assert fresh.form.operator_entries_known
    assert fresh.form.layout_provenance is not ModeloFormLayoutProvenance.INSPECTION_ONLY
    assert _field(fresh.form, "06").origin is not ModeloFormOrigin.ENTERED
    assert _field(fresh.form, "06").editability is ModeloFormEditability.EDITABLE_VALUE
    entered = _field(edited.form, "06")
    assert entered.origin is ModeloFormOrigin.ENTERED
    assert entered.value == Decimal("100")
    assert _field(recalculated.form, "06").origin is ModeloFormOrigin.ENTERED
    assert _field(recalculated.form, "06").editability is ModeloFormEditability.NO_ADMISSION
    derived = _field(recalculated.form, "07")
    assert derived.origin is ModeloFormOrigin.CALCULATED
    assert derived.value == Decimal("-100.00")
    assert recalculated.form.calculation_revision_id is not None
    assert not edited.verified
    assert not edited.filed


def test_only_the_registry_declared_target_of_the_projection_offers_it(tmp_path: Path) -> None:
    """The annual return of the year the projection was authored for offers the estimate; nothing else does.

    The quarterly declaration the estimate is built from, and the annual return of a
    year whose revision the projection declaration was not authored against, do not.
    """
    with seeded_operator_work(tmp_path / "annual", modelo="100", filing_year=2025, period_code="0A") as work:
        assert _load(work, None).form.projectable is True
    with seeded_operator_work(tmp_path / "quarter", modelo="130", filing_year=2025, period_code="1T") as work:
        assert _load(work, None).form.projectable is False
    with seeded_operator_work(tmp_path / "earlier", modelo="100", filing_year=2024, period_code="0A") as work:
        assert _load(work, None).form.projectable is False


def test_each_box_says_where_its_edit_is_submitted(tmp_path: Path) -> None:
    """Box 05 carries the instalments of earlier declarations; replacing it is an override of that binding.

    Box 06 is a value the filer types, edited at the box itself. Neither holds an
    assumed value, so neither is confirmable, and the form's envelope carries all three.
    """
    with seeded_operator_work(tmp_path) as work:
        fresh = _load(work, work.admit())

    carried = _field(fresh.form, "05")
    typed = _field(fresh.form, "06")
    assert carried.editability is ModeloFormEditability.OVERRIDABLE_SOURCE
    assert carried.edit_address == ModeloFormBindingAddressV1(binding_id=carried.bindings[0].binding_id)
    assert typed.editability is ModeloFormEditability.EDITABLE_VALUE
    assert typed.edit_address == typed.address
    assert not carried.confirmable
    assert not typed.confirmable


def test_an_admission_for_another_declaration_offers_nothing(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as work:
        other = work.sibling("2T")
        form = _load(work, other.admit()).form

    assert _field(form, "06").editability is ModeloFormEditability.NO_ADMISSION
    assert not form.edit_admitted


def _needs_input(form: ModeloWorkForm) -> set[str]:
    return {
        key[1]
        for key in (address_key(item.address) for item in form.fields() if item.origin is ModeloFormOrigin.NEEDS_INPUT)
    }


def test_the_form_asks_for_exactly_what_the_real_verification_finds_missing(tmp_path: Path) -> None:
    """Verification is the authority on what the filer owes, so the two never disagree.

    The operator supplies the previous Renta's economic-activity income,
    without entering a box. Box 06 is a box the filer types
    and sits in the calculation closure the completeness manifest lists; the
    form used to ask for every empty box of that closure, 06 included, while
    verification, which follows the registry's required flag, never asks for
    it.
    """
    with seeded_operator_work(tmp_path) as work:
        fresh = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form
        applied = work.apply(
            binding=tuple(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=binding_id),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=value,
                )
                for binding_id, value in (
                    ("irpf.previous_year_economic_activity_net_income", "13000"),
                    ("modelo-130-resultados-negativos-anteriores", "0"),
                    ("modelo-130-pagos-fraccionados-anteriores", "0"),
                )
            )
        )
        assert applied.refusal is None
        work.recalculate()
        _verify(work)
        verified = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form
        manifest = work.operation.snapshot("130", filing_year=2026, period="1T").revision.completeness_manifest

    missing = {
        str(issue.finding.casilla_id)
        for issue in verified.issues
        if issue.finding.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    }
    assert verified.verification is not None, "the verification did not run, so this proves nothing"
    assert _needs_input(fresh) == _needs_input(verified) == missing
    assert manifest is not None
    assert "06" in {str(item.casilla_id) for item in manifest.casillas}
    assert _field(fresh, "06").value is None
    assert _field(fresh, "06").origin is ModeloFormOrigin.OPTIONAL_EMPTY
    assert not _field(fresh, "06").required

    # The previous Renta is supplied and the fresh ledger holds no income,
    # so the declared result is a calculated zero.
    assert verified.result is not None
    assert verified.result.box == "19"
    assert _field(verified, "19").origin is ModeloFormOrigin.CALCULATED
    assert verified.result.value == Decimal("0")
    assert verified.result.direction is ModeloFormResultDirection.NIL

    assert verified.deadline is not None
    assert verified.deadline.nominal_closes_on == date(2026, 4, 20)
    assert verified.deadline.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert verified.deadline.days_remaining == (verified.deadline.closes_on - _REFERENCE_DAY).days


def test_a_form_with_unsatisfied_prior_renta_keeps_unknown_result_and_refuses_verification(tmp_path: Path) -> None:
    """Box 13 waits on last year's Modelo 100, which is not recorded, so nothing can be verified yet.

    Verification refuses through the blocking-note gate on the prior-filing note, and the form keeps
    the quarter's result unknown rather than presenting a figure.
    """
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        with pytest.raises(ModeloCalculationBlockedError) as refused:
            _verify(work)
        form = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form

    context = refused.value.context or {}
    assert context["reason"] == "unresolved_binding"
    assert context["box"] == "13"
    (note,) = (
        issue
        for issue in blocking_calculation_issues(head)
        if issue.fact is not None and issue.fact.sentence is CalculationNoteSentence.PRIOR_FILING_UNRECORDED
    )
    assert note.casilla_id == "13"
    assert note.fact is not None
    assert dict(note.fact.values) == {"box": "13", "modelo": "100", "year": str(_REFERENCE_DAY.year - 1)}
    assert form.result is not None
    assert form.result.box == "19"
    assert _field(form, "19").origin is ModeloFormOrigin.CALCULATION_FAILED
    assert form.result.value is None
    assert form.result.direction is ModeloFormResultDirection.UNKNOWN


def test_a_declaration_recorded_as_filed_offers_nothing_for_editing(tmp_path: Path) -> None:
    """Neither the admission nor the edit executor refuses a filed head, so the form does.

    The head is really calculated and admitted; only its lifecycle is moved to
    filed, as recording the filing moves it, because a filing needs a clean
    verification this synthetic taxpayer cannot have.
    """
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        review = _review(work)
        open_form = _rebuilt(work, head, review)
        filed_head = head.model_copy(update={"state": CalculationRevisionState.PRESENTADO, "filed_at": _FILED_AT})
        filed_form = _rebuilt(
            work, filed_head, review.model_copy(update={"lifecycle_state": CalculationRevisionState.PRESENTADO})
        )

    assert open_form.edit_admitted
    assert open_form.edit_closure is None
    assert open_form.filing is None
    assert _field(open_form, "06").editability is ModeloFormEditability.EDITABLE_VALUE

    assert filed_form.edit_closure is ModeloFormEditClosure.RECORDED_AS_FILED
    assert filed_form.filing is not None
    assert filed_form.filing.recorded_at == _FILED_AT
    assert not filed_form.edit_admitted
    assert _field(filed_form, "06").editability is ModeloFormEditability.NO_ADMISSION
    assert not any(item.editability in _EDITABLE for item in filed_form.fields())


def test_values_a_replayed_aeat_draft_supplied_read_as_aeat_data(tmp_path: Path) -> None:
    """A recalculation replays the imported draft, so the form says which boxes it fed and when."""
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        review = _review(work)
        plain = _rebuilt(work, head, review)
        records_binding = _field(plain, "01").bindings[0].binding_id
        replayed = head.model_copy(
            update={"borrador_snapshot_id": _SNAPSHOT_ID, "bindings_sourced_from_borrador": (records_binding,)}
        )
        from_draft = _rebuilt(work, replayed, review)

    assert plain.aeat_data is None
    plain_source = _field(plain, "01").source
    assert plain_source is not None
    assert plain_source.family is SourceFamily.RECORDS

    assert from_draft.aeat_data is not None
    assert from_draft.aeat_data.snapshot_id == _SNAPSHOT_ID
    assert from_draft.aeat_data.imported_at == _IMPORTED_AT
    assert from_draft.aeat_data.binding_ids == (records_binding,)
    draft_source = _field(from_draft, "01").source
    assert draft_source is not None
    assert draft_source.family is SourceFamily.AEAT_DRAFT
    assert draft_source.binding_id == records_binding
    # Box 02 is worked out from the prior expenses; that working figure is the records-fed field.
    other_source = _field(from_draft, "gastos-deducibles-previos").source
    assert other_source is not None
    assert other_source.family is SourceFamily.RECORDS


def test_an_unrecorded_modality_leaves_box_02_open_and_says_so(tmp_path: Path) -> None:
    """Box 02 under the simplified modality adds a provision, so an unrecorded modality cannot be guessed.

    The calculation still finishes. Box 02 and every box built on it stay open, and the
    calculation carries a note that withholds filing until the filer records the modality.
    """
    with seeded_operator_work(tmp_path, estimation_regime=None) as work:
        work.recalculate()
        form = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form

    assert _field(form, "02").origin is ModeloFormOrigin.CALCULATION_FAILED
    assert _field(form, "provisiones-gastos-dificil-justificacion").origin is ModeloFormOrigin.CALCULATION_FAILED
    assert _field(form, "19").origin is ModeloFormOrigin.CALCULATION_FAILED
    assert any(note.reason == "unresolved_binding" for note in form.blocking_calculation_notes), form.calculation_notes


def test_an_unrecorded_modality_note_names_box_02_and_the_profile_fact_in_served_words(tmp_path: Path) -> None:
    """The note and its check line say which box waits and which profile fact answers it, in the filer's words.

    The calculation raises it on the profile's own unanswered binding, so it must reach the form
    through the held diagnostics and, once the process forgets them, through the revision itself.
    """
    with seeded_operator_work(tmp_path, estimation_regime=None) as work:
        head = work.recalculate()
        held = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form
        CALCULATION_NOTES.record(head.work_unit_id, "forgotten", ())
        reopened = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form

    for form in (held, reopened):
        (note,) = (
            item
            for item in form.blocking_calculation_notes
            if item.fact is not None and item.fact.sentence is CalculationNoteSentence.PROFILE_FACT_UNRECORDED
        )
        assert note.reason == "unresolved_binding"
        assert note.casilla_id == "02"
        assert note.box == "02"
        assert note.fact is not None
        assert dict(note.fact.values) == {"box": "02", "field": "irpf.estimation_regime"}
        (line,) = (
            item
            for item in form_issue_lines(form, OutputLanguage.ES)
            if item.address == ModeloFormCasillaAddressV1(casilla_id=_C02) and item.from_calculation
        )
        assert line.message == "Para calcular la casilla 02, registra en tu perfil: Régimen de estimación."
        assert line.box == "02"
        assert line.address == ModeloFormCasillaAddressV1(casilla_id=_C02)
        assert "unresolved_binding" in line.technical


def test_an_unrecorded_prior_year_modelo_100_note_names_box_13_and_the_filing_in_served_words(tmp_path: Path) -> None:
    """Box 13 waits on the previous year's net activity income, so the note says which filing to record.

    The activity began years before the quarter and the store holds no Modelo 100, so nothing can
    stand for the prior year's income. The note must carry its box and the filing, not a bare reason,
    both from the held diagnostics and, once the process forgets them, from the revision itself.
    """
    with seeded_operator_work(tmp_path) as work:
        head = work.recalculate()
        held = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form
        CALCULATION_NOTES.record(head.work_unit_id, "forgotten", ())
        reopened = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form

    for form in (held, reopened):
        (note,) = (
            item
            for item in form.blocking_calculation_notes
            if item.fact is not None and item.fact.sentence is CalculationNoteSentence.PRIOR_FILING_UNRECORDED
        )
        assert note.reason == "unresolved_binding"
        assert note.casilla_id == "13"
        assert note.box == "13"
        assert note.fact is not None
        assert dict(note.fact.values) == {"box": "13", "modelo": "100", "year": str(_REFERENCE_DAY.year - 1)}
        assert not [
            item
            for item in form.blocking_calculation_notes
            if item.reason == "unresolved_binding" and item.casilla_id is None and item.fact is None
        ]
        (line,) = (
            item
            for item in form_issue_lines(form, OutputLanguage.ES)
            if item.address == ModeloFormCasillaAddressV1(casilla_id=_C13) and item.from_calculation
        )
        assert line.message == "Para calcular la casilla 13, registra tu Modelo 100 de 2025."
        assert line.box == "13"
        assert "unresolved_binding" in line.technical
