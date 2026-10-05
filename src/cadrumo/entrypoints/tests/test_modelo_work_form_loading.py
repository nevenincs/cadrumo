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

from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ...adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ...application.modelo.edit_models import (
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloScalarEditIntentV1,
)
from ...application.modelo.operation_definitions import (
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloWorkVerifyExecutor,
    resolve_active_workflow_profile,
)
from ...application.modelo.source_policy import SourceFamily
from ...application.modelo.work_form import build_modelo_work_form
from ...application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloWorkForm,
    address_key,
)
from ...application.modelo.work_form_service import ModeloWorkFormLoadV1, load_modelo_work_form, modelo_form_snapshot
from ...application.modelo.work_review import ModeloWorkReview, build_modelo_work_review
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.owner import OperationExecutorContext
from ...core.casilla_id import validated_casilla_id
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.operations import OperationEffect
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.verification_report import ModeloVerificationFindingKind
from ..adapter_composition import build_verification_repository_bundle
from .modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_C06 = validated_casilla_id("06")
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


@dataclass(slots=True)
class _Events:
    phases: list[str] = field(default_factory=list)
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


@dataclass(frozen=True, slots=True)
class _Context:
    """The slice of the supervisor context the verify executor reads."""

    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    events: _Events


def _verify(work: SeededOperatorWork) -> None:
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
        events=_Events(),
    )
    executor = ModeloWorkVerifyExecutor(
        certificate_secret_backend_factory=build_certificate_secret_backend,
        profile_resolver=resolve_active_workflow_profile,
        operator_scope_ports=build_operator_scope_ports(),
        verification_repository_bundle_factory=build_verification_repository_bundle,
    )
    report_id = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    assert report_id is not None


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


@pytest.mark.timeout(240)
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


@pytest.mark.timeout(240)
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


@pytest.mark.timeout(240)
def test_the_form_asks_for_exactly_what_the_real_verification_finds_missing(tmp_path: Path) -> None:
    """Verification is the authority on what the filer owes, so the two never disagree.

    Nobody enters anything, so the verification of the calculation judges the
    same entries the uncalculated form shows. Box 06 is a box the filer types
    and sits in the calculation closure the completeness manifest lists; the
    form used to ask for every empty box of that closure, 06 included, while
    verification, which follows the registry's required flag, never asks for
    it.
    """
    with seeded_operator_work(tmp_path) as work:
        fresh = _load(work, work.admit(), reference_on=_REFERENCE_DAY).form
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

    # The engine could not produce the result without the earlier Renta it
    # reads, so the box holds nothing and no direction is claimed for it.
    assert verified.result is not None
    assert verified.result.box == "19"
    assert _field(verified, "19").origin is ModeloFormOrigin.CALCULATION_FAILED
    assert verified.result.value is None
    assert verified.result.direction is ModeloFormResultDirection.UNKNOWN

    assert verified.deadline is not None
    assert verified.deadline.nominal_closes_on == date(2026, 4, 20)
    assert verified.deadline.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert verified.deadline.days_remaining == (verified.deadline.closes_on - _REFERENCE_DAY).days


@pytest.mark.timeout(240)
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


@pytest.mark.timeout(240)
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
    other_source = _field(from_draft, "02").source
    assert other_source is not None
    assert other_source.family is SourceFamily.RECORDS
