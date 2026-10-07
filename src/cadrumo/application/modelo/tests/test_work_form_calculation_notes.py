"""What the latest calculation noticed reaches the editor form on the filer's scale, and a box it could not work out never reads as zero.

Built by the real read model over the published authority for a Modelo 130
first quarter, with diagnostics of the shapes the calculation raises. A box
the form prints whose source produced nothing is worth checking, persists
with the calculation, and reads as not calculated instead of holding its zero.
An amount from the records that reached no box blocks filing. A note that a finding of the
check already says, about the same box, is shown once, as the finding. When
this session did not run the latest calculation, only the notes that persist
with it are known, and the form says so.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.schema import ModeloValueKind
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from ..work_form import build_modelo_work_form
from ..work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO, _YEAR, _QUARTER = "130", 2026, "1T"
_PRINTED = "01"
_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_WORK_UNIT = "c" * 64


def _snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    period = Period.from_year_and_code(_YEAR, _QUARTER)
    revision_id = str(operation.revision_for_context(_MODELO, filing_year=_YEAR, period=_QUARTER).id)
    return modelo_form_snapshot(operation, ModeloCode(_MODELO), _YEAR, period, revision_id)


def _review(
    operation: PinnedAuthorityOperation,
    snapshot: RegistrySnapshot,
    *,
    zero_at: str | None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
    calculation_revision_id: str | None = None,
    verification_outcome: VerificationCompletenessStatus | None = None,
) -> ModeloWorkReview:
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    return ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000130",
        modelo=_MODELO,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _QUARTER),
        registry_revision_id=snapshot.revision.id,
        work_unit_id=_WORK_UNIT,
        calculation_revision_id=calculation_revision_id,
        lifecycle_state=None,
        verification_outcome=verification_outcome,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=tuple(
            # The engine's silent zero, as a box whose source produced nothing would otherwise hold.
            row.model_copy(update={"value": Decimal("0"), "realised_kind": ModeloValueKind.LITERAL})
            if str(row.casilla_id) == zero_at
            else row
            for row in rows
        ),
        findings=findings,
        blockers=(),
    )


def _form(
    operation: PinnedAuthorityOperation,
    *,
    diagnostics: tuple[CalculationSourceDiagnostic, ...] | None,
    zero_at: str | None = None,
    findings: tuple[ModeloVerificationFinding, ...] = (),
    revision: CalculationRevision | None = None,
    verification_outcome: VerificationCompletenessStatus | None = None,
) -> ModeloWorkForm:
    snapshot = _snapshot(operation)
    return build_modelo_work_form(
        review=_review(
            operation,
            snapshot,
            zero_at=zero_at,
            findings=findings,
            calculation_revision_id=None if revision is None else revision.calculation_revision_id,
            verification_outcome=verification_outcome,
        ),
        snapshot=snapshot,
        layout=operation.form_layout(_MODELO, snapshot.revision.id),
        revision=revision,
        permitted_surface=None,
        entered_casilla_ids=frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
        calculation_diagnostics=diagnostics,
    )


def _unresolved(casilla_id: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="unresolved_binding",
        source_kind="ledger_renta_income_aggregation",
        casilla_id=casilla_id,
        message=f"binding for casilla {casilla_id!r} produced no value",
    )


def _field(form: ModeloWorkForm, casilla_id: str) -> ModeloFormField:
    return next(field for field in form.fields() if address_key(field.address) == ("casilla", casilla_id))


def _working_figure(operation: PinnedAuthorityOperation) -> str:
    """A casilla the form keeps among its working figures, with no printed box."""
    form = _form(operation, diagnostics=())
    return next(key[1] for key in (address_key(field.address) for field in form.working_figures) if key[0] == "casilla")


def test_a_printed_box_that_could_not_be_worked_out_blocks_filing_and_never_reads_as_zero(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _form(operation, diagnostics=(_unresolved(_PRINTED),), zero_at=_PRINTED)
    field = _field(form, _PRINTED)

    note = ModeloFormCalculationNote(
        reason="unresolved_binding",
        attention=ModeloFormAttention.BLOCKS,
        casilla_id=_PRINTED,
        box=_PRINTED,
    )
    assert form.calculation_notes == (note,)
    assert form.blocking_calculation_notes == (note,)
    assert field.origin is ModeloFormOrigin.CALCULATION_FAILED
    assert field.value is None
    assert form.calculation_notes_held


def test_the_same_box_without_a_note_keeps_its_value(operation: PinnedAuthorityOperation) -> None:
    """Teeth for the rule above: only the note turns the zero into "could not be worked out"."""
    field = _field(_form(operation, diagnostics=(), zero_at=_PRINTED), _PRINTED)

    assert field.origin is not ModeloFormOrigin.CALCULATION_FAILED
    assert field.value == Decimal("0")


def test_a_working_figure_that_could_not_be_worked_out_is_worth_checking(
    operation: PinnedAuthorityOperation,
) -> None:
    """Teeth for the rule above: the same reason on a box the form does not print withholds nothing."""
    working = _working_figure(operation)
    form = _form(operation, diagnostics=(_unresolved(working),))
    (note,) = form.calculation_notes

    assert note.attention is ModeloFormAttention.CHECK
    assert form.blocking_calculation_notes == ()
    assert note.box is None


def test_a_note_the_check_already_makes_about_the_same_box_is_shown_once_as_the_finding(
    operation: PinnedAuthorityOperation,
) -> None:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=_PRINTED,
        message_locale_key="application.modelo.findings.missing_required_casilla",
        message_facts={"casilla_id": _PRINTED},
        legal_refs=("rd-439-2007:art-110",),
    )
    other_box = _form(operation, diagnostics=(_unresolved("03"),), findings=(finding,))
    same_box = _form(operation, diagnostics=(_unresolved(_PRINTED),), findings=(finding,))

    assert same_box.calculation_notes == ()
    assert len(same_box.issues) == 1
    assert [note.casilla_id for note in other_box.calculation_notes] == ["03"]


def test_each_reason_takes_its_place_on_the_scale_most_urgent_first(operation: PinnedAuthorityOperation) -> None:
    diagnostics = (
        CalculationSourceDiagnostic(reason="oss_no_live_source", source_kind="oss", message="no OSS invoice"),
        CalculationSourceDiagnostic(
            reason="operator_override_diverges_from_computed",
            source_kind="operator",
            casilla_id="03",
            message="the typed value differs",
        ),
        CalculationSourceDiagnostic(
            reason="unrouted_observation", source_kind="ledger", message="an amount reached no box"
        ),
        CalculationSourceDiagnostic(
            reason="unrouted_observation", source_kind="ledger", message="an amount reached no box"
        ),
    )
    notes = _form(operation, diagnostics=diagnostics).calculation_notes

    assert [(note.reason, note.attention) for note in notes] == [
        ("unrouted_observation", ModeloFormAttention.BLOCKS),
        ("operator_override_diverges_from_computed", ModeloFormAttention.CHECK),
        ("oss_no_live_source", ModeloFormAttention.INFO),
    ]


def _revision_with_issues(
    snapshot: RegistrySnapshot, issues: tuple[CalculationSourceIssue, ...]
) -> CalculationRevision:
    revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_issues=issues,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_WORK_UNIT,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=_MODELO, revision_id=snapshot.revision.id, modelo_year=_YEAR, period=_QUARTER
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
    )


def test_a_declaration_opened_afresh_knows_only_the_notes_that_persist_with_its_calculation(
    operation: PinnedAuthorityOperation,
) -> None:
    persisted = CalculationSourceIssue(
        reason="unresolved_binding",
        binding_source=None,
        message="binding for casilla '01' produced no value",
        casilla_id=_PRINTED,
    )
    revision = _revision_with_issues(_snapshot(operation), (persisted,))
    form = _form(operation, diagnostics=None, zero_at=_PRINTED, revision=revision)

    assert not form.calculation_notes_held
    assert [(note.reason, note.box, note.attention) for note in form.calculation_notes] == [
        ("unresolved_binding", _PRINTED, ModeloFormAttention.BLOCKS)
    ]
    assert _field(form, _PRINTED).value is None


def test_an_amount_that_reached_no_box_blocks_filing(operation: PinnedAuthorityOperation) -> None:
    unrouted = CalculationSourceDiagnostic(
        reason="unrouted_declarable_quantity", source_kind="ledger_iva_aggregation", message="a base reached no box"
    )
    form = _form(operation, diagnostics=(unrouted,))

    assert [(note.reason, note.attention) for note in form.blocking_calculation_notes] == [
        ("unrouted_declarable_quantity", ModeloFormAttention.BLOCKS)
    ]


def _scope_evidence_failure() -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="iva_selected_scope_evidence_failure",
        source_kind="ledger_iva_aggregation",
        message="a ledger IVA row's selected filing scope cannot be completed from its evidence",
    )


def test_a_note_only_the_check_decides_blocks_until_the_calculation_is_checked(
    operation: PinnedAuthorityOperation,
) -> None:
    unchecked = _form(operation, diagnostics=(_scope_evidence_failure(),))

    assert [(note.reason, note.attention) for note in unchecked.blocking_calculation_notes] == [
        ("iva_selected_scope_evidence_failure", ModeloFormAttention.BLOCKS)
    ]


@pytest.mark.parametrize("verdict", list(VerificationCompletenessStatus))
def test_once_checked_a_note_only_the_check_decides_gives_way_to_the_check_even_where_it_found_nothing(
    operation: PinnedAuthorityOperation, verdict: VerificationCompletenessStatus
) -> None:
    """The check's report is what stands; a cause it accepted without a finding blocks nothing."""
    checked = _form(operation, diagnostics=(_scope_evidence_failure(),), verification_outcome=verdict)

    assert "iva_selected_scope_evidence_failure" not in {note.reason for note in checked.calculation_notes}
    assert checked.blocking_calculation_notes == ()


def test_once_checked_a_note_the_check_does_not_decide_still_blocks(operation: PinnedAuthorityOperation) -> None:
    """Teeth for the rule above: only the check's own reasons give way to it."""
    unrouted = CalculationSourceDiagnostic(
        reason="unrouted_observation",
        source_kind="ledger_iva_aggregation",
        message="a row no binding consumes",
    )
    checked = _form(operation, diagnostics=(unrouted,), verification_outcome=VerificationCompletenessStatus.COMPLETE)

    assert [note.reason for note in checked.blocking_calculation_notes] == ["unrouted_observation"]


@pytest.mark.parametrize("entered", [True, False])
def test_retained_bound_casilla_override_is_displayed_even_when_its_source_is_unresolved(
    operation: PinnedAuthorityOperation, entered: bool
) -> None:
    snapshot = _snapshot(operation)
    rows = build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation)
    amount = Decimal("355926.98")
    review = _review(operation, snapshot, zero_at=None).model_copy(
        update={
            "casillas": tuple(
                row.model_copy(update={"value": amount, "realised_kind": ModeloValueKind.INHERITED})
                if str(row.casilla_id) == "05"
                else row
                for row in rows
            ),
        }
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(_MODELO, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=frozenset({validated_casilla_id("05")}) if entered else frozenset(),
        overridden_binding_ids=frozenset(),
        language=OutputLanguage.EN,
        calculation_diagnostics=(_unresolved("05"),),
    )
    field = _field(form, "05")
    if entered:
        assert field.value == amount
        assert field.origin is ModeloFormOrigin.OVERRIDES_SOURCE
    else:
        assert field.value is None
        assert field.origin is ModeloFormOrigin.CALCULATION_FAILED
    assert any(
        note.casilla_id == "05" and note.attention is ModeloFormAttention.BLOCKS for note in form.calculation_notes
    )
