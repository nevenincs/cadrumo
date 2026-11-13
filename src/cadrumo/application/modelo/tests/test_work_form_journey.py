"""The form serves where a declaration stands on the filing journey, so no frontend decides it.

Every form is a Modelo 210 built by the real builder over the published registry;
each case states the one lifecycle fact it is about and reads the journey the
application serves with the form: which steps are done, which is current or
blocked, the next step while a refused apply's prerequisite stands, the first
box that needs the filer, the verdict's wording and the action each export hold
names.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ..calculation_notes import CHECK_REFUSED_REASONS, GATE_REFUSED_REASONS
from ..work_form_declaration_facts import ModeloFormCalculationNote
from ..work_form_field_vocabulary import ModeloFormStanding
from ..work_form_findings import ModeloFormAttention
from ..work_form_header import ModeloFormExportHoldReason, export_hold
from ..work_form_journey import ModeloFormStep, ModeloFormStepStatus, form_journey
from ..work_form_models import ModeloWorkForm, section_fields
from ..work_form_next_step import ModeloFormNextAction, held_prerequisite_step
from ..work_form_service import modelo_work_form_load
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INCOME = "rendimientos_integros"
_KIND = "tipo_renta"
_HELD: dict[str, Decimal | str] = {_INCOME: Decimal("1200.00"), _KIND: "01"}
_DONE = ModeloFormStepStatus.DONE
_CURRENT = ModeloFormStepStatus.CURRENT
_BLOCKED = ModeloFormStepStatus.BLOCKED
_PENDING = ModeloFormStepStatus.PENDING


def _empty(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    return built_form(operation, "210", 2025, "0A", entered=frozenset())


def _entered(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    return built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset(_HELD))


def _calculated(form: ModeloWorkForm, **update: object) -> ModeloWorkForm:
    return form.model_copy(update={"calculation_revision_id": "c" * 64, **update})


def _statuses(form: ModeloWorkForm, *, verified: bool = False, filed: bool = False) -> list[ModeloFormStepStatus]:
    return [state.status for state in form_journey(form, verified=verified, filed=filed).steps]


def _note(reason: str) -> ModeloFormCalculationNote:
    return ModeloFormCalculationNote(reason=reason, attention=ModeloFormAttention.BLOCKS)


def test_the_steps_are_the_four_of_the_journey_in_order(operation: PinnedAuthorityOperation) -> None:
    journey = form_journey(_empty(operation), verified=False, filed=False)

    assert [state.step for state in journey.steps] == list(ModeloFormStep)
    assert [state.step for state in journey.steps_while_changes_held] == list(ModeloFormStep)


def test_each_lifecycle_fact_marks_the_steps_it_settles(operation: PinnedAuthorityOperation) -> None:
    entered = _entered(operation)
    assumed = built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset({_KIND}))
    complete = VerificationCompletenessStatus.COMPLETE
    filed = built_form(operation, "210", 2025, "0A", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)

    assert _statuses(_empty(operation)) == [_CURRENT, _PENDING, _PENDING, _PENDING]
    assert _statuses(entered) == [_DONE, _CURRENT, _PENDING, _PENDING]
    assert _statuses(_calculated(entered)) == [_DONE, _DONE, _CURRENT, _PENDING]
    assert _statuses(_calculated(entered, verification=complete), verified=True) == [_DONE, _DONE, _DONE, _CURRENT]
    # An assumed value keeps filling in open on a verified declaration, and the later steps still show as done.
    assert _statuses(_calculated(assumed, verification=complete), verified=True) == [_CURRENT, _DONE, _DONE, _PENDING]
    assert _statuses(_calculated(filed), verified=True, filed=True) == [_DONE, _DONE, _DONE, _DONE]


def test_a_step_done_shows_as_done_after_the_current_one(operation: PinnedAuthorityOperation) -> None:
    form = _calculated(_empty(operation))

    assert _statuses(form) == [_CURRENT, _DONE, _PENDING, _PENDING]


def test_a_note_only_the_check_decides_leaves_the_check_current_and_a_gate_note_blocks_it(
    operation: PinnedAuthorityOperation,
) -> None:
    entered = _entered(operation)
    check_note = sorted(CHECK_REFUSED_REASONS)[0]
    gate_note = sorted(GATE_REFUSED_REASONS - CHECK_REFUSED_REASONS)[0]

    awaiting = _calculated(entered, calculation_notes=(_note(check_note),))
    refused = _calculated(entered, calculation_notes=(_note(gate_note),))

    assert _statuses(awaiting)[2] is _CURRENT
    assert _statuses(refused)[2] is _BLOCKED


def test_a_check_that_found_the_declaration_blocked_blocks_the_check_step(operation: PinnedAuthorityOperation) -> None:
    form = _calculated(_entered(operation), verification=VerificationCompletenessStatus.BLOCKED)

    assert _statuses(form)[2] is _BLOCKED


def test_changes_the_frontend_holds_undo_every_step(operation: PinnedAuthorityOperation) -> None:
    form = _calculated(_entered(operation), verification=VerificationCompletenessStatus.COMPLETE)

    journey = form_journey(form, verified=True, filed=True)

    assert _DONE in [state.status for state in journey.steps]
    held = [state.status for state in journey.steps_while_changes_held]
    assert held == [_CURRENT, _PENDING, _PENDING, _PENDING]


def test_the_next_step_while_a_prerequisite_stands_is_resolving_it_from_the_findings(
    operation: PinnedAuthorityOperation,
) -> None:
    for form, verified in ((_empty(operation), False), (_entered(operation), True)):
        journey = form_journey(form, verified=verified, filed=False)

        assert journey.held_prerequisite_next_step == held_prerequisite_step(journey.next_step)
        assert journey.held_prerequisite_next_step.action is ModeloFormNextAction.RESOLVE
        assert journey.held_prerequisite_next_step.findings_lead


def test_the_first_attention_is_the_first_box_that_stands_on_the_filer(operation: PinnedAuthorityOperation) -> None:
    form = _empty(operation)
    first = next(
        (page.id, field)
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if field.standing is ModeloFormStanding.NEEDS_YOU
    )

    attention = form_journey(form, verified=False, filed=False).first_attention

    assert attention is not None
    assert (attention.page_id, attention.address) == (first[0], first[1].address)


def test_nothing_is_the_first_attention_when_nothing_stands_on_the_filer(operation: PinnedAuthorityOperation) -> None:
    entered = _entered(operation)

    assert form_journey(entered, verified=False, filed=False).first_attention is None


def test_a_declaration_recorded_as_filed_has_no_first_attention(operation: PinnedAuthorityOperation) -> None:
    form = _empty(operation)

    assert form_journey(form, verified=True, filed=True).first_attention is None


def test_a_page_that_does_not_apply_is_skipped_for_the_first_attention(operation: PinnedAuthorityOperation) -> None:
    form = _empty(operation)
    holding = [
        index
        for index, page in enumerate(form.pages)
        if any(
            field.standing is ModeloFormStanding.NEEDS_YOU
            for section in page.sections
            for field in section_fields(section)
        )
    ]
    assert holding
    unchanged = form_journey(form, verified=False, filed=False).first_attention
    assert unchanged is not None

    pages = tuple(
        page.model_copy(update={"applies": False}) if index == holding[0] else page
        for index, page in enumerate(form.pages)
    )
    skipped = form_journey(form.model_copy(update={"pages": pages}), verified=False, filed=False).first_attention

    assert skipped is None or skipped.page_id != form.pages[holding[0]].id


def test_the_load_carries_the_journey_of_its_form_and_lifecycle(operation: PinnedAuthorityOperation) -> None:
    form = _entered(operation)

    load = modelo_work_form_load(form, verified=True, filed=False)

    assert load.journey == form_journey(form, verified=True, filed=False)


@pytest.mark.parametrize("status", list(VerificationCompletenessStatus))
def test_a_finished_check_is_worded_and_leads_to_the_findings_unless_it_is_complete(
    operation: PinnedAuthorityOperation, status: VerificationCompletenessStatus
) -> None:
    form = _calculated(_entered(operation), verification=status)

    verdict = form_journey(form, verified=False, filed=False).verdict

    assert verdict.status is status
    assert verdict.checked_words is not None and verdict.checked_words
    assert verdict.checked_resolves is (status is not VerificationCompletenessStatus.COMPLETE)


def test_a_declaration_not_checked_has_no_finished_check_words(operation: PinnedAuthorityOperation) -> None:
    verdict = form_journey(_entered(operation), verified=False, filed=False).verdict

    assert verdict.status is None
    assert verdict.checked_words is None
    assert not verdict.checked_resolves


def test_each_export_hold_names_the_action_that_lifts_it(operation: PinnedAuthorityOperation) -> None:
    gate_note = sorted(GATE_REFUSED_REASONS)[0]
    assumed = _calculated(built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset({_KIND})))
    blocked = _calculated(_entered(operation), calculation_notes=(_note(gate_note),))
    unchecked = _calculated(_entered(operation))
    language = unchecked.language

    holds = {
        ModeloFormExportHoldReason.BLOCKS: export_hold(blocked, language, verified=True, recorded=False),
        ModeloFormExportHoldReason.CONFIRM: export_hold(assumed, language, verified=True, recorded=False),
        ModeloFormExportHoldReason.VERIFY: export_hold(unchecked, language, verified=False, recorded=False),
    }
    actions = {reason: None if hold is None else (hold.reason, hold.action) for reason, hold in holds.items()}

    assert actions == {
        ModeloFormExportHoldReason.BLOCKS: (ModeloFormExportHoldReason.BLOCKS, ModeloFormNextAction.RESOLVE),
        ModeloFormExportHoldReason.CONFIRM: (ModeloFormExportHoldReason.CONFIRM, ModeloFormNextAction.CONFIRM),
        ModeloFormExportHoldReason.VERIFY: (ModeloFormExportHoldReason.VERIFY, ModeloFormNextAction.VERIFY),
    }
